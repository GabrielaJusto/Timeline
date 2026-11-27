from pathlib import Path
from django.http import FileResponse
from django.views.decorators.http import require_GET
import base64
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from cryptography.hazmat.primitives import serialization
import json
from urllib.parse import urlsplit
from django.views.decorators.http import require_POST
from .models import InscricaoPush

@require_GET
def service_worker(request):
    caminho = (
        Path(__file__).resolve().parent
        / "static"
        / "js"
        / "service-worker.js"
    )

    resposta = FileResponse(
        open(caminho, "rb"),
        content_type="application/javascript"
    )

    resposta["Service-Worker-Allowed"] = "/"
    resposta["Cache-Control"] = "no-cache"

    return resposta

@login_required
@require_GET
def chave_publica_push(request):
    if not settings.VAPID_PUBLIC_KEY.is_file():
        return JsonResponse(
            {"erro": "Chave VAPID não configurada."},
            status=503
        )

    chave = serialization.load_pem_public_key(
        settings.VAPID_PUBLIC_KEY.read_bytes()
    )

    chave_publica = base64.urlsafe_b64encode(
        chave.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
    ).decode().rstrip("=")

    return JsonResponse({
        "chave_publica": chave_publica
    })

@login_required
@require_POST
def inscrever_push(request):
    try:
        dados = json.loads(request.body)

        endpoint = dados["endpoint"]
        p256dh = dados["keys"]["p256dh"]
        auth = dados["keys"]["auth"]

        url = urlsplit(endpoint)

        if (
            url.scheme != "https"
            or url.netloc != "fcm.googleapis.com"
            or not url.path.startswith("/fcm/send/")
            or len(endpoint) > 2048
            or not p256dh
            or not auth
            or len(p256dh) > 255
            or len(auth) > 255
        ):
            raise ValueError

    except (KeyError, ValueError, TypeError, AttributeError):
        return JsonResponse(
            {"erro": "Inscrição inválida."},
            status=400
        )

    InscricaoPush.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "usuario": request.user,
            "p256dh": p256dh,
            "auth": auth
        }
    )

    request.session["push_endpoint"] = endpoint

    return JsonResponse({"sucesso": True})

@login_required
@require_POST
def cancelar_push(request):
    try:
        dados = json.loads(request.body)
        endpoint = dados["endpoint"]

        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError

    except (KeyError, ValueError, TypeError):
        return JsonResponse(
            {"erro": "Inscrição inválida."},
            status=400
        )

    InscricaoPush.objects.filter(
        usuario=request.user,
        endpoint=endpoint
    ).delete()

    return JsonResponse({"sucesso": True})

@login_required
@require_POST
def status_push(request):
    try:
        dados = json.loads(request.body)
        endpoint = dados["endpoint"]

        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError

    except (KeyError, ValueError, TypeError):
        return JsonResponse(
            {"erro": "Inscrição inválida."},
            status=400
        )

    ativo = InscricaoPush.objects.filter(
        usuario=request.user,
        endpoint=endpoint
    ).exists()

    if ativo:
        request.session["push_endpoint"] = endpoint

    return JsonResponse({"ativo": ativo})