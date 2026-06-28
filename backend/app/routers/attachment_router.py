import logging
import subprocess
import tempfile
import os
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies.app_auth import get_aula_service
from app.services.aula_service import AulaService

_LOGGER = logging.getLogger(__name__)

CONVERTIBLE_EXTENSIONS = {"doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp"}


def create_attachment_router() -> APIRouter:
    router = APIRouter(tags=["attachments"])

    @router.get("/attachments/as-pdf")
    async def convert_to_pdf(
        url: str,
        name: str = "document",
        aula_service: AulaService = Depends(get_aula_service),
    ):
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in CONVERTIBLE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="File type not supported for conversion")

        # Fetch the file from Aula
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                file_bytes = response.content
        except Exception as e:
            _LOGGER.error(f"Failed to fetch attachment: {e}")
            raise HTTPException(status_code=502, detail="Could not fetch attachment from Aula")

        pdf_name = os.path.splitext(name)[0] + ".pdf"

        # Convert via unoconvert (talks to the persistent unoserver process)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, name)
            pdf_path = os.path.join(tmpdir, pdf_name)
            with open(input_path, "wb") as f:
                f.write(file_bytes)

            try:
                result = subprocess.run(
                    ["unoconvert", "--convert-to", "pdf", input_path, pdf_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    _LOGGER.error(f"unoconvert failed: {result.stderr}")
                    raise HTTPException(status_code=500, detail="PDF conversion failed")
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="PDF conversion timed out")

            if not os.path.exists(pdf_path):
                raise HTTPException(status_code=500, detail="PDF output not found after conversion")

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

        encoded_name = urllib.parse.quote(pdf_name)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    return router



def create_attachment_router() -> APIRouter:
    router = APIRouter(tags=["attachments"])

    @router.get("/attachments/as-pdf")
    async def convert_to_pdf(
        url: str,
        name: str = "document",
        aula_service: AulaService = Depends(get_aula_service),
    ):
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in CONVERTIBLE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="File type not supported for conversion")

        pdf_name = os.path.splitext(name)[0] + ".pdf"

        # Return cached PDF if available
        cached = _cache_get(url)
        if cached:
            _LOGGER.debug(f"Serving cached PDF for {name}")
            pdf_bytes, pdf_name = cached
            encoded_name = urllib.parse.quote(pdf_name)
            return StreamingResponse(
                iter([pdf_bytes]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                    "Content-Length": str(len(pdf_bytes)),
                },
            )

        # Fetch the file from Aula
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                file_bytes = response.content
        except Exception as e:
            _LOGGER.error(f"Failed to fetch attachment: {e}")
            raise HTTPException(status_code=502, detail="Could not fetch attachment from Aula")

        # Convert to PDF via LibreOffice in a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, name)
            with open(input_path, "wb") as f:
                f.write(file_bytes)

            try:
                result = subprocess.run(
                    [
                        "libreoffice", "--headless", "--convert-to", "pdf",
                        "--outdir", tmpdir, input_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    _LOGGER.error(f"LibreOffice conversion failed: {result.stderr}")
                    raise HTTPException(status_code=500, detail="PDF conversion failed")
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="PDF conversion timed out")

            pdf_path = os.path.join(tmpdir, pdf_name)
            if not os.path.exists(pdf_path):
                raise HTTPException(status_code=500, detail="PDF output not found after conversion")

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

        _cache_set(url, pdf_bytes, pdf_name)

        encoded_name = urllib.parse.quote(pdf_name)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    return router
