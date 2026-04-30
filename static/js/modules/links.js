/**
 * Link Library module – manage internal link targets.
 */

import { api } from '../api.js';
import { showAlert, escapeHtml } from '../ui.js';
import { userLinks, setUserLinks } from './state.js';

let editingLinkId = null;

export async function initLinkLibrary() {
  const addBtn = document.getElementById('add-link-btn');
  const cancelBtn = document.getElementById('cancel-edit-link-btn');
  if (!addBtn) return;

  addBtn.addEventListener('click', handleAddOrUpdateLink);
  cancelBtn.addEventListener('click', cancelEditLink);

  await loadLinks();
}

async function loadLinks() {
  try {
    const data = await api.getLinks();
    setUserLinks(data.links || []);
    renderLinkList();
  } catch (e) {
    console.error('Error loading links:', e);
  }
}

function renderLinkList() {
  const container = document.getElementById('link-library-list');
  if (!container) return;

  if (userLinks.length === 0) {
    container.innerHTML = '<div class="link-library-empty"><span class="material-icons-outlined" style="vertical-align:-3px;margin-right:4px;font-size:1.1rem">link_off</span>Nog geen links toegevoegd</div>';
    return;
  }

  container.innerHTML = userLinks.map(link => `
    <div class="link-library-item" data-id="${link.id}">
      <div class="link-library-item-info">
        <span class="link-library-item-label">
          <span class="material-icons-outlined">link</span>
          ${escapeHtml(link.label)}
        </span>
        <a href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" class="link-library-item-url">
          ${escapeHtml(link.url)}
        </a>
        ${link.description ? `<span class="link-library-item-desc">${escapeHtml(link.description)}</span>` : ''}
      </div>
      <div class="link-library-item-actions">
        <button type="button" class="btn-icon" title="Bewerken" data-edit-link="${link.id}">
          <span class="material-icons-outlined">edit</span>
        </button>
        <button type="button" class="btn-icon btn-icon-danger" title="Verwijderen" data-delete-link="${link.id}">
          <span class="material-icons-outlined">delete_outline</span>
        </button>
      </div>
    </div>
  `).join('');

  container.querySelectorAll('[data-edit-link]').forEach(btn => {
    btn.addEventListener('click', () => startEditLink(parseInt(btn.dataset.editLink)));
  });
  container.querySelectorAll('[data-delete-link]').forEach(btn => {
    btn.addEventListener('click', () => handleDeleteLink(parseInt(btn.dataset.deleteLink)));
  });
}

async function handleAddOrUpdateLink() {
  const urlInput = document.getElementById('linkUrl');
  const labelInput = document.getElementById('linkLabel');
  const descInput = document.getElementById('linkDescription');
  const url = urlInput.value.trim();
  const label = labelInput.value.trim();
  const description = descInput.value.trim();

  if (!url || !label) {
    showAlert('URL en label zijn verplicht.', 'error');
    return;
  }

  try {
    if (editingLinkId) {
      await api.updateLink(editingLinkId, url, label, description);
      showAlert('Link bijgewerkt.', 'success');
      cancelEditLink();
    } else {
      await api.createLink(url, label, description);
      showAlert('Link toegevoegd.', 'success');
    }
    urlInput.value = '';
    labelInput.value = '';
    descInput.value = '';
    await loadLinks();
  } catch (e) {
    showAlert(e.message || 'Fout bij opslaan van link.', 'error');
  }
}

function startEditLink(linkId) {
  const link = userLinks.find(l => l.id === linkId);
  if (!link) return;

  editingLinkId = linkId;
  document.getElementById('linkUrl').value = link.url;
  document.getElementById('linkLabel').value = link.label;
  document.getElementById('linkDescription').value = link.description || '';
  document.getElementById('add-link-btn').innerHTML =
    '<span class="material-icons-outlined">save</span> Opslaan';
  document.getElementById('cancel-edit-link-btn').classList.remove('hidden');
  document.getElementById('link-library-add-block').style.borderColor = 'var(--color-primary-300)';
}

function cancelEditLink() {
  editingLinkId = null;
  document.getElementById('linkUrl').value = '';
  document.getElementById('linkLabel').value = '';
  document.getElementById('linkDescription').value = '';
  document.getElementById('add-link-btn').innerHTML =
    '<span class="material-icons-outlined">add_link</span> Toevoegen';
  document.getElementById('cancel-edit-link-btn').classList.add('hidden');
  document.getElementById('link-library-add-block').style.borderColor = '';
}

async function handleDeleteLink(linkId) {
  if (!confirm('Weet je zeker dat je deze link wilt verwijderen?')) return;
  try {
    await api.deleteLink(linkId);
    showAlert('Link verwijderd.', 'success');
    await loadLinks();
  } catch (e) {
    showAlert(e.message || 'Fout bij verwijderen.', 'error');
  }
}
