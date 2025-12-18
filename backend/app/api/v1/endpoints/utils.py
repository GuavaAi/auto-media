from __future__ import annotations

import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from email.utils import formatdate
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, FileResponse
from fastapi.responses import HTMLResponse
from bs4 import BeautifulSoup
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import deps
from app.services.api_key_pool import pick_api_key
from app.services.crawler import RequestsCrawler, PlaywrightCrawler, discover_links

router = APIRouter()


class DiscoverLinksResponse(BaseModel):
    """发现子页面链接响应"""
    links: List[str]


@router.get("/discover-links", response_model=DiscoverLinksResponse, summary="发现子页面链接")
def discover_sub_links(
    url: str = Query(..., description="目标页面 URL"),
    limit: int = Query(10, ge=1, le=100, description="最多返回链接数"),
    use_playwright: bool = Query(False, description="是否使用 Playwright 渲染"),
    css_selector: str = Query("", description="主页面过滤 CSS 选择器，仅在该区域内发现链接"),
) -> DiscoverLinksResponse:
    """
    抓取目标页面并发现同域子页面链接，用于元素选择器预览子页面。
    如果传入 css_selector，则仅在过滤后的内容区域内发现链接。
    """
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=400, detail="url 必须以 http:// 或 https:// 开头")

    crawler = PlaywrightCrawler() if use_playwright else RequestsCrawler()
    try:
        res = crawler.fetch(u)
        html = res.html or ""
        final_url = (res.extra or {}).get("final_url") or u
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"抓取页面失败：{exc}") from exc

    # 构建 parser_cfg，用于在过滤后的内容区域内发现链接
    parser_cfg = None
    if css_selector and css_selector.strip():
        parser_cfg = {"css_selector": css_selector.strip()}

    links = discover_links(html, final_url, budget=limit, seen_set={u, final_url}, parser_cfg=parser_cfg)
    return DiscoverLinksResponse(links=links)


@router.get("/page-preview", response_class=HTMLResponse, summary="页面预览（用于元素选择器）")
def page_preview(
    url: str = Query(..., description="目标页面 URL"),
    use_playwright: bool = Query(False, description="是否使用 Playwright 渲染"),
) -> HTMLResponse:
    """返回可被前端 iframe(srcdoc) 渲染的 HTML，并注入元素选择器脚本。"""

    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=400, detail="url 必须以 http:// 或 https:// 开头")

    # 说明：此预览 HTML 仅用于“选择元素生成 CSS Selector”，不是生产抓取结果。
    # - 为避免执行外站脚本，这里会移除 <script>
    # - 注入 base 标签保证相对资源可加载
    crawler = PlaywrightCrawler() if use_playwright else RequestsCrawler()
    try:
        res = crawler.fetch(u)
        html = res.html
        final_url = (res.extra or {}).get("final_url") or u
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"抓取预览页面失败：{exc}") from exc

    soup = BeautifulSoup(html or "", "html.parser")

    # 移除 CSP，避免影响 iframe 中的预览渲染
    for meta in soup.find_all("meta"):
        http_equiv = (meta.get("http-equiv") or "").strip().lower()
        if http_equiv == "content-security-policy":
            meta.decompose()

    # 移除脚本，避免外站脚本在预览中执行
    for s in soup.find_all("script"):
        s.decompose()

    if soup.head is None:
        head = soup.new_tag("head")
        if soup.html is None:
            html_tag = soup.new_tag("html")
            soup.append(html_tag)
        soup.html.insert(0, head)

    # base：保证相对路径资源（css/img）在预览中尽量可用
    base_tag = soup.new_tag("base", href=str(final_url))
    soup.head.insert(0, base_tag)

    style_tag = soup.new_tag("style")
    style_tag["data-element-picker"] = "1"
    style_tag.string = """
      #__element_picker_overlay__{position:fixed;left:0;top:0;width:0;height:0;pointer-events:none;z-index:2147483647;border:2px solid #409EFF;background:rgba(64,158,255,.15);box-sizing:border-box;}
      #__element_picker_hint__{position:fixed;left:12px;bottom:12px;z-index:2147483647;background:rgba(0,0,0,.72);color:#fff;padding:8px 10px;border-radius:6px;font:12px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;}
      #__element_picker_hint__ code{color:#fff;}
    """
    soup.head.append(style_tag)

    script_tag = soup.new_tag("script")
    script_tag["data-element-picker"] = "1"
    script_tag.string = """
      (function(){
        try {
          var overlay = document.getElementById('__element_picker_overlay__');
          if(!overlay){
            overlay = document.createElement('div');
            overlay.id='__element_picker_overlay__';
            document.documentElement.appendChild(overlay);
          }
          var hint = document.getElementById('__element_picker_hint__');
          if(!hint){
            hint = document.createElement('div');
            hint.id='__element_picker_hint__';
            hint.innerHTML='点击页面元素以生成 CSS Selector，按 <code>Esc</code> 取消';
            document.documentElement.appendChild(hint);
          }

          function isOurNode(el){
            if(!el) return false;
            return el.id==='__element_picker_overlay__' || el.id==='__element_picker_hint__';
          }

          // 优先 id/class 选择器，仅在无法唯一确定时才降级到结构路径
          function isUnique(sel){
            try{ return document.querySelectorAll(sel).length===1; }catch(e){ return false; }
          }

          function getClasses(el){
            // 过滤掉常见无意义/动态 class
            var skip = /^(active|hover|focus|show|hide|open|close|visible|hidden|is-|has-|js-|no-|ng-|v-|el-|ant-|css-|_|[0-9])/i;
            var list = [];
            for(var i=0;i<el.classList.length;i++){
              var c = el.classList[i];
              if(c && !skip.test(c)) list.push(c);
            }
            return list;
          }

          function cssPath(el){
            if(!el || el.nodeType!==1) return '';

            // 1) 优先：元素自身有 id
            if(el.id){
              var idSel = '#'+CSS.escape(el.id);
              if(isUnique(idSel)) return idSel;
            }

            // 2) 尝试用 class 组合（最多取前 3 个有效 class）
            var classes = getClasses(el);
            if(classes.length){
              var tag = el.tagName.toLowerCase();
              // 尝试 tag + 全部 class
              var classSel = tag + '.' + classes.slice(0,3).map(function(c){return CSS.escape(c);}).join('.');
              if(isUnique(classSel)) return classSel;
              // 尝试仅 class
              classSel = '.' + classes.slice(0,3).map(function(c){return CSS.escape(c);}).join('.');
              if(isUnique(classSel)) return classSel;
            }

            // 3) 向上查找祖先 id/class 作为锚点，再拼接子路径
            var parts = [];
            var cur = el;
            while(cur && cur.nodeType===1 && cur.tagName.toLowerCase()!=='html'){
              var tag = cur.tagName.toLowerCase();

              // 祖先有 id，直接作为锚点
              if(cur.id){
                parts.unshift('#'+CSS.escape(cur.id));
                break;
              }

              // 祖先有可用 class，尝试作为锚点
              var anc = getClasses(cur);
              if(anc.length){
                var ancSel = tag + '.' + anc.slice(0,2).map(function(c){return CSS.escape(c);}).join('.');
                var full = ancSel + (parts.length ? ' > ' + parts.join(' > ') : '');
                if(isUnique(full)){
                  parts.unshift(ancSel);
                  break;
                }
              }

              // 降级：nth-of-type
              var parent = cur.parentElement;
              var nth = 1;
              if(parent){
                var siblings = parent.children;
                for(var i=0;i<siblings.length;i++){
                  if(siblings[i]===cur) break;
                  if(siblings[i].tagName===cur.tagName) nth++;
                }
              }
              parts.unshift(tag+':nth-of-type('+nth+')');
              cur = parent;
            }
            return parts.join(' > ');
          }

          function updateOverlay(target){
            if(!target || isOurNode(target)){
              overlay.style.width='0px';
              overlay.style.height='0px';
              return;
            }
            var r = target.getBoundingClientRect();
            overlay.style.left = Math.max(0, r.left) + 'px';
            overlay.style.top = Math.max(0, r.top) + 'px';
            overlay.style.width = Math.max(0, r.width) + 'px';
            overlay.style.height = Math.max(0, r.height) + 'px';
          }

          document.addEventListener('mousemove', function(e){
            updateOverlay(e.target);
          }, true);

          document.addEventListener('click', function(e){
            if(isOurNode(e.target)) return;
            e.preventDefault();
            e.stopPropagation();
            var sel = cssPath(e.target);
            window.parent && window.parent.postMessage({type:'element-picked', selector: sel}, '*');
          }, true);

          document.addEventListener('keydown', function(e){
            if(e.key==='Escape'){
              window.parent && window.parent.postMessage({type:'element-picker-cancel'}, '*');
            }
          }, true);
        } catch(err) {
          // 忽略预览注入异常，避免影响页面展示
        }
      })();
    """
    soup.body.append(script_tag) if soup.body else soup.append(script_tag)

    return HTMLResponse(content=str(soup), status_code=200)


class UploadImageResponse(BaseModel):
    url: str
    key: str


@router.post("/upload-image", response_model=UploadImageResponse, summary="上传图片（用于封面/素材）")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
) -> UploadImageResponse:
    """上传图片并返回可访问 URL。

    中文说明：
    - 当前实现为本地存储（backend/uploads），便于开发联调。
    - 生产环境可替换为 OSS/S3 等对象存储，并保持返回 url 为公网可访问地址。
    """

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持上传图片文件")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大（最大 10MB）")

    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
    if not suffix:
        guessed = mimetypes.guess_extension(content_type) or ""
        suffix = guessed

    # 中文说明：
    # 1) 优先环境变量（便于容器部署/快速排障）
    # 2) 其次从 APIKey 池 provider=oss 取（统一配置中心）
    oss_endpoint = (os.getenv("OSS_ENDPOINT") or "").strip()
    oss_bucket = (os.getenv("OSS_BUCKET") or "").strip()
    oss_access_key_id = (os.getenv("OSS_ACCESS_KEY_ID") or "").strip()
    oss_access_key_secret = (os.getenv("OSS_ACCESS_KEY_SECRET") or "").strip()
    oss_prefix = (os.getenv("OSS_PREFIX") or "").strip()
    oss_public_base = (os.getenv("OSS_PUBLIC_BASE_URL") or "").strip().rstrip("/")

    if not (oss_endpoint and oss_bucket and oss_access_key_id and oss_access_key_secret):
        try:
            k = pick_api_key(db, "oss", mark_used=True)
        except Exception:
            k = None

        if k and isinstance(getattr(k, "extra", None), dict):
            extra = k.extra or {}

            # 中文说明：兼容不同字段命名（snake/camel）
            oss_endpoint = oss_endpoint or str(extra.get("endpoint") or extra.get("oss_endpoint") or "").strip()
            oss_bucket = oss_bucket or str(extra.get("bucket") or extra.get("oss_bucket") or "").strip()
            oss_access_key_id = oss_access_key_id or str(
                extra.get("access_key_id")
                or extra.get("accessKeyId")
                or extra.get("accessKeyID")
                or extra.get("oss_access_key_id")
                or ""
            ).strip()
            oss_access_key_secret = oss_access_key_secret or str(
                extra.get("access_key_secret")
                or extra.get("accessKeySecret")
                or extra.get("accessKeySECRET")
                or extra.get("oss_access_key_secret")
                or ""
            ).strip()
            if not oss_access_key_secret:
                oss_access_key_secret = (k.key or "").strip()

            oss_prefix = oss_prefix or str(extra.get("prefix") or extra.get("oss_prefix") or "").strip()
            if not oss_public_base:
                oss_public_base = str(
                    extra.get("public_base_url")
                    or extra.get("publicBaseUrl")
                    or extra.get("public_base")
                    or extra.get("cdn")
                    or ""
                ).strip().rstrip("/")

    if not oss_prefix:
        oss_prefix = "uploads/"

    if oss_endpoint and oss_bucket and oss_access_key_id and oss_access_key_secret:
        try:
            import oss2  # type: ignore
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"OSS 依赖未安装或导入失败：{exc}") from exc

        obj_key = f"{oss_prefix.rstrip('/')}/{uuid.uuid4().hex}{suffix}" if oss_prefix else f"{uuid.uuid4().hex}{suffix}"
        auth = oss2.Auth(oss_access_key_id, oss_access_key_secret)
        bucket = oss2.Bucket(auth, oss_endpoint, oss_bucket)
        try:
            bucket.put_object(obj_key, raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"上传 OSS 失败：{exc}") from exc

        if oss_public_base:
            url = f"{oss_public_base}/{obj_key.lstrip('/')}"
        else:
            ep = oss_endpoint
            if ep.startswith("http://"):
                ep = ep[len("http://") :]
            if ep.startswith("https://"):
                ep = ep[len("https://") :]
            url = f"https://{oss_bucket}.{ep.rstrip('/')}/{obj_key.lstrip('/')}"
        return UploadImageResponse(url=url, key=obj_key)

    backend_root = Path(__file__).resolve().parents[4]
    uploads_dir = Path(os.getenv("UPLOADS_DIR") or (backend_root / "uploads"))
    uploads_dir.mkdir(parents=True, exist_ok=True)

    key = f"{uuid.uuid4().hex}{suffix}"
    path = uploads_dir / key
    path.write_bytes(raw)

    base = str(request.base_url).rstrip("/")
    url = f"{base}/api/utils/uploads/{key}"
    return UploadImageResponse(url=url, key=key)


@router.get("/uploads/{key}", summary="访问已上传图片", response_class=FileResponse, response_model=None)
def get_uploaded_image(key: str, request: Request):
    backend_root = Path(__file__).resolve().parents[4]
    uploads_dir = Path(os.getenv("UPLOADS_DIR") or (backend_root / "uploads"))

    safe_key = os.path.basename(key)
    path = uploads_dir / safe_key
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    st = path.stat()
    etag = f'W/"{st.st_mtime_ns}-{st.st_size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    media_type, _ = mimetypes.guess_type(str(path))
    resp = FileResponse(str(path), media_type=media_type or "application/octet-stream")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["ETag"] = etag
    resp.headers["Last-Modified"] = formatdate(st.st_mtime, usegmt=True)
    return resp
