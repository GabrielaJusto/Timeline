document.addEventListener("DOMContentLoaded", async function () {
    const botao = document.getElementById("botao-push");
    const status = document.getElementById("status-push");

    if (!botao || !status) return;

    if (
        !("serviceWorker" in navigator) ||
        !("PushManager" in window) ||
        !("Notification" in window)
    ) {
        status.textContent = "Navegador não compatível.";
        return;
    }

    const csrf = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    ).value;

    async function enviarDados(url, dados) {
        const resposta = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf
            },
            body: JSON.stringify(dados)
        });

        if (!resposta.ok) {
            throw new Error("Não foi possível salvar a configuração.");
        }

        return resposta.json();
    }

    try {
        const registro = await navigator.serviceWorker.ready;
        let inscricao = await registro.pushManager.getSubscription();

        if (inscricao) {
            const dados = await enviarDados("/push/status/", {
                endpoint: inscricao.endpoint
            });

            if (!dados.ativo) {
                await inscricao.unsubscribe();
                inscricao = null;
            }
        }

        function atualizarInterface() {
            status.textContent = inscricao
                ? "Notificações ativadas neste navegador"
                : "Notificações desativadas";

            botao.textContent = inscricao
                ? "Desativar notificações"
                : "Ativar notificações";
        }

        atualizarInterface();
        botao.disabled = false;

        botao.addEventListener("click", async function () {
            botao.disabled = true;

            try {
                if (inscricao) {
                    await enviarDados("/push/cancelar/", {
                        endpoint: inscricao.endpoint
                    });

                    await inscricao.unsubscribe();
                    inscricao = null;

                } else {
                    const permissao = await Notification.requestPermission();

                    if (permissao !== "granted") {
                        throw new Error("Permissão não concedida.");
                    }

                    const resposta = await fetch("/push/chave-publica/");

                    if (!resposta.ok) {
                        throw new Error("Chave pública indisponível.");
                    }

                    const dados = await resposta.json();

                    const novaInscricao = await registro.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: dados.chave_publica
                    });

                    try {
                        await enviarDados(
                            "/push/inscrever/",
                            novaInscricao.toJSON()
                        );

                        inscricao = novaInscricao;

                    } catch (erro) {
                        await novaInscricao.unsubscribe();
                        throw erro;
                    }
                }

                atualizarInterface();

            } catch (erro) {
                status.textContent = erro.message;

            } finally {
                botao.disabled = false;
            }
        });

    } catch (erro) {
        status.textContent = "Erro ao configurar notificações.";
    }
});