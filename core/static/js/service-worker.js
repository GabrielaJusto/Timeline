self.addEventListener("push", function (event) {
    const dados = event.data ? event.data.json() : {};

    const titulo = dados.titulo || "Timeline";

    const opcoes = {
        body: dados.mensagem || "Você tem um novo lembrete!",
        data: {
            url: "/tarefas/"
        }
    };

    event.waitUntil(
        self.registration.showNotification(titulo, opcoes)
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (janelas) {
            for (const janela of janelas) {
                if (janela.url === new URL("/tarefas/", self.location.origin).href) {
                    return janela.focus();
                }
            }

            return clients.openWindow("/tarefas/");
        })
    );
});
