(() => {
  const endpoint = new URL(document.currentScript.dataset.endpoint, location.href);
  let active = null;
  document.addEventListener('click', async (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== endpoint.origin || url.pathname !== endpoint.pathname) return;
    event.preventDefault();
    if (active) return;

    const dialog = document.createElement('dialog');
    dialog.className = 'notificacoes-modal';
    dialog.setAttribute('aria-label', 'Notificações');
    const host = document.createElement('div');
    dialog.append(host);
    const shadow = host.attachShadow({mode: 'open'});
    shadow.innerHTML = `<style>
      :host {font-family:Arial,sans-serif;color:#111936}
      .modal-toolbar {display:flex;justify-content:flex-end;padding:16px 20px 0}
      .modal-close {border:0;border-radius:8px;background:#eeeeff;color:#4845bc;padding:8px 12px;font:600 14px Arial,sans-serif;cursor:pointer}
      .modal-close:hover {background:#dfddff}
      .modal-close:focus-visible {outline:3px solid #5a59dd;outline-offset:3px}
      .modal-status {padding:24px;line-height:1.6}
      .conteudo-notificacoes {margin:0;padding:8px 24px 24px;max-width:none}
      .conteudo-notificacoes header {margin-bottom:24px}
      .conteudo-notificacoes h1 {font-size:26px}
    </style>
    <div class="modal-toolbar"><button class="modal-close" type="button" aria-label="Fechar notificações">Fechar ×</button></div>
    <div class="modal-content"><p class="modal-status" role="status">Carregando notificações…</p></div>`;
    const close = shadow.querySelector('.modal-close');
    const content = shadow.querySelector('.modal-content');
    const previousOverflow = document.body.style.overflow;
    active = dialog;
    const closeDialog = () => {
      dialog.close();
      cleanup();
    };
    close.addEventListener('click', closeDialog);
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      closeDialog();
    });
    dialog.addEventListener('click', (e) => {
      if (e.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (e.clientX < bounds.left || e.clientX > bounds.right || e.clientY < bounds.top || e.clientY > bounds.bottom) closeDialog();
    });
    const controller = new AbortController();
    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      controller.abort();
      document.body.style.overflow = previousOverflow;
      dialog.remove();
      active = null;
      link.focus();
    };
    dialog.addEventListener('close', cleanup);
    document.body.append(dialog);
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    close.focus();
    try {
      const response = await fetch(endpoint, {signal: controller.signal});
      if (response.redirected && new URL(response.url).pathname !== endpoint.pathname) {
        location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error('Falha ao carregar');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const main = page.querySelector('.conteudo-notificacoes');
      if (!main) throw new Error('Conteúdo indisponível');
      const css = page.querySelector('link[href*="css/notificacoes.css"]');
      if (css) shadow.prepend(css.cloneNode(true));
      content.replaceChildren(main);
    } catch (error) {
      if (error.name === 'AbortError') return;
      content.innerHTML = '<p class="modal-status" role="alert">Não foi possível carregar as notificações. Feche e tente novamente.</p>';
    }
  });
})();
