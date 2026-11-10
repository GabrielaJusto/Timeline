(() => {
  const script = document.currentScript;
  const endpoint = new URL(script.dataset.endpoint, location.href);
  let active = null;
  document.addEventListener('click', async (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== endpoint.origin || url.pathname !== endpoint.pathname) return;
    event.preventDefault();
    if (active) return;
    const dialog = document.createElement('dialog');
    active = dialog;
    dialog.setAttribute('aria-label', 'Adicionar tarefa');
    dialog.style.cssText = 'position:fixed;inset:0;margin:auto;padding:0;border:0;border-radius:15px;width:min(580px,calc(100vw - 32px));height:fit-content;max-width:none;max-height:90vh;overflow:auto;background:white;';
    const host = document.createElement('div');
    dialog.append(host);
    const shadow = host.attachShadow({mode:'open'});
    const previousOverflow = document.body.style.overflow;
    dialog.addEventListener('close', () => {
      document.body.style.overflow = previousOverflow;
      dialog.remove(); active = null; link.focus();
    });
    document.body.append(dialog);
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    shadow.innerHTML = '<p role="status" style="padding:24px">Carregando...</p>';
    const render = (html) => {
      const page = new DOMParser().parseFromString(html, 'text/html');
      const modal = page.querySelector('.modal');
      if (!modal) throw new Error('Formulario indisponivel');
      shadow.replaceChildren();
      for (const css of page.querySelectorAll('link[rel="stylesheet"]')) shadow.append(css.cloneNode(true));
      const style = document.createElement('style');
      style.textContent = ':host{display:block;font-family:Arial,sans-serif;color:#111936}.modal{position:static;transform:none;width:100%;max-height:none;box-shadow:none;border-radius:0;margin:0}';
      shadow.append(style, modal);
      modal.querySelector('input:not([type="hidden"]),select')?.focus();
    };
    shadow.addEventListener('click', (e) => {
      if (e.target.closest('.fechar,.cancelar')) { e.preventDefault(); dialog.close(); }
    });
    shadow.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const button = form.querySelector('[type="submit"]');
      button.disabled = true;
      try {
        const response = await fetch(endpoint, {method:'POST', body:new FormData(form), headers:{'X-Task-Modal':'1'}});
        if (!response.ok) throw new Error('Falha ao salvar');
        if (response.headers.get('content-type')?.includes('application/json')) {
          location.assign((await response.json()).redirect);
        } else render(await response.text());
      } catch (error) {
        button.disabled = false;
        let message = shadow.querySelector('[role="alert"]');
        if (!message) { message = document.createElement('p'); message.setAttribute('role','alert'); form.prepend(message); }
        message.textContent = 'Nao foi possivel salvar. Tente novamente.';
      }
    });
    try {
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error('Falha ao abrir');
      render(await response.text());
    } catch (error) {
      shadow.innerHTML = '<p style="padding:24px" role="alert">Nao foi possivel abrir o formulario. Feche e tente novamente.</p><button class="fechar">Fechar</button>';
    }
  });
})();
