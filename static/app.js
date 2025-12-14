function $(selector, context = document) { return context.querySelector(selector); }
function $all(selector, context = document) { return Array.from(context.querySelectorAll(selector)); }

function initAuthTabs() {
  const tabs = document.querySelector('.auth__tabs');
  if (!tabs) return;
  const loginForm = $('#login-form');
  const registerForm = $('#register-form');
  const active = tabs.dataset.active || 'login';
  switchTab(active);
  tabs.addEventListener('click', (e) => {
    if (e.target.dataset.tab) {
      switchTab(e.target.dataset.tab);
    }
  });
  document.body.addEventListener('click', (e) => {
    if (e.target.dataset.switch) {
      e.preventDefault();
      switchTab(e.target.dataset.switch);
    }
  });

  function switchTab(tab) {
    tabs.dataset.active = tab;
    $all('.tab', tabs).forEach(btn => btn.classList.toggle('is-active', btn.dataset.tab === tab));
    loginForm.classList.toggle('is-hidden', tab !== 'login');
    registerForm.classList.toggle('is-hidden', tab !== 'register');
  }
}

function initToasts() {
  const container = $('#toast-container');
  if (!container) return;
  setTimeout(() => container.classList.add('fade'), 4000);
  setTimeout(() => container.remove(), 5200);
}

function initSelectAll() {
  const master = $('#select-all');
  if (!master) return;
  master.addEventListener('change', () => {
    $all('.row-check').forEach(chk => chk.checked = master.checked);
  });
}

function initBulkMove() {
  const form = $('#bulk-form');
  if (!form) return;
  form.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-action="move"]');
    if (!btn) return;
    const target = prompt('Zielordner (relativ zum Home):', '');
    if (target === null) { e.preventDefault(); return; }
    $('#bulk-target').value = target;
  });
}

function initFolderButtons() {
  document.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    if (!action) return;
    const path = e.target.dataset.path || '';
    if (action === 'new-folder') {
      const name = prompt('Ordnername');
      if (!name) return;
      postForm('/folders/create', { path, name });
    } else if (action === 'rename-folder') {
      const name = prompt('Neuer Ordnername');
      if (!name) return;
      postForm('/folders/rename', { path, name });
    } else if (action === 'delete-folder') {
      if (!confirm('Diesen Ordner wirklich löschen? (muss leer sein)')) return;
      postForm('/folders/delete', { path });
    }
  });
}

function postForm(url, data) {
  const form = document.createElement('form');
  form.method = 'post';
  form.action = url;
  Object.entries(data).forEach(([key, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = value;
    form.appendChild(input);
  });
  document.body.appendChild(form);
  form.submit();
}

function initDropzone(formId, inputId, progressSelector) {
  const form = document.getElementById(formId);
  const input = document.getElementById(inputId);
  const container = progressSelector ? document.getElementById(progressSelector) : null;
  const bar = container ? (container.querySelector('.progress__bar') || container) : null;
  if (!form || !input) return;

  form.addEventListener('dragover', (e) => { e.preventDefault(); form.classList.add('is-drag'); });
  form.addEventListener('dragleave', () => form.classList.remove('is-drag'));
  form.addEventListener('drop', (e) => {
    e.preventDefault();
    form.classList.remove('is-drag');
    input.files = e.dataTransfer.files;
  });

  form.addEventListener('submit', (e) => {
    if (!input.files.length) return;
    e.preventDefault();
    const fd = new FormData(form);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', form.action, true);
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && bar) {
        const pct = Math.round((evt.loaded / evt.total) * 100);
        bar.style.width = pct + '%';
      }
    };
    xhr.onload = () => { window.location.reload(); };
    xhr.send(fd);
  });
}

function init() {
  initAuthTabs();
  initToasts();
  initSelectAll();
  initBulkMove();
  initFolderButtons();
  initDropzone('quick-upload', 'quick-files', 'quick-progress');
  initDropzone('upload-form', 'upload-files', 'upload-progress');
}

document.addEventListener('DOMContentLoaded', init);
