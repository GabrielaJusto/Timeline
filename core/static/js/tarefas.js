(() => {
  const form = document.getElementById('lote');
  if (!form) return;
  const all = document.getElementById('selecionar-todas');
  const boxes = Array.from(form.elements).filter(el => el.name === 'atividades');
  const action = form.elements.namedItem('acao');
  const date = form.elements.namedItem('nova_data');
  const button = document.getElementById('aplicar-lote');
  function sync() {
    const count = boxes.filter(box => box.checked).length;
    document.getElementById('quantidade-selecionadas').textContent = `${count} selecionadas`;
    all.checked = boxes.length > 0 && count === boxes.length;
    all.indeterminate = count > 0 && count < boxes.length;
    button.disabled = count === 0;
    date.required = action.value === 'adiar';
    date.disabled = action.value !== 'adiar';
  }
  all.addEventListener('change', () => { boxes.forEach(box => { box.checked = all.checked; }); sync(); });
  boxes.forEach(box => box.addEventListener('change', sync));
  action.addEventListener('change', sync);
  form.addEventListener('submit', event => {
    if (!boxes.some(box => box.checked) || (action.value === 'excluir' && !confirm('Mover as tarefas selecionadas para a lixeira?'))) event.preventDefault();
  });
  window.addEventListener('pageshow', sync);
  sync();
})();
