/**
 * Translation module – draft translation management.
 */

import { api } from '../api.js';
import { showAlert, showModal, setButtonLoading, escapeHtml } from '../ui.js';
import { activeDraftId, saveCurrentDraft } from './state.js';

const AVAILABLE_LANGUAGES = [
  { code: 'en', label: 'Engels', flag: '🇬🇧' },
  { code: 'de', label: 'Duits', flag: '🇩🇪' },
  { code: 'fr', label: 'Frans', flag: '🇫🇷' },
  { code: 'es', label: 'Spaans', flag: '🇪🇸' },
];

export async function openTranslateModal() {
  if (!activeDraftId) {
    showAlert('Laad eerst een concept om te vertalen.', 'error');
    return;
  }

  await saveCurrentDraft({ silent: true });

  let existingTranslations = [];
  try {
    const resp = await api.getDraftTranslations(activeDraftId);
    existingTranslations = resp.translations || [];
  } catch (e) {
    console.error('Error fetching translations:', e);
  }

  const existingLangs = new Set(existingTranslations.map(t => t.language));

  const languageRows = AVAILABLE_LANGUAGES.map(lang => {
    const exists = existingLangs.has(lang.code);
    const badge = exists
      ? `<span class="badge badge-primary" style="margin-left:8px;font-size:0.75rem;">Vertaling aanwezig</span>`
      : '';
    return `
      <label class="form-checkbox" style="display:flex;align-items:center;gap:8px;padding:8px 0;">
        <input type="checkbox" name="translate-lang" value="${lang.code}" checked />
        <span>${lang.flag} ${lang.label}${badge}</span>
      </label>
    `;
  }).join('');

  const content = `
    <div style="display:flex;flex-direction:column;gap:16px;">
      <p style="margin:0;color:#555;">Selecteer de talen waarnaar je dit concept wilt vertalen.</p>
      <div>${languageRows}</div>
      <label class="form-checkbox" style="display:flex;align-items:center;gap:8px;">
        <input type="checkbox" id="translate-image-check" checked />
        <span>Afbeelding ook vertalen (als er tekst in staat)</span>
      </label>
      <div id="translate-status" style="display:none;"></div>
    </div>
  `;

  const footer = `
    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Annuleren</button>
    <button class="btn btn-primary" id="translate-submit-btn">
      <span class="material-icons-outlined" style="font-size:1.1rem;">translate</span>
      Vertalen
    </button>
  `;

  showModal('Blog vertalen', content, footer);

  const submitBtn = document.getElementById('translate-submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      const checked = document.querySelectorAll('input[name="translate-lang"]:checked');
      const languages = Array.from(checked).map(el => el.value);
      const translateImage = document.getElementById('translate-image-check')?.checked ?? true;
      const statusDiv = document.getElementById('translate-status');

      if (languages.length === 0) {
        showAlert('Selecteer minimaal één taal.', 'error');
        return;
      }

      setButtonLoading(submitBtn, true);
      statusDiv.style.display = 'block';
      statusDiv.innerHTML = '<div style="padding:12px;background:#eff6ff;border-left:4px solid #3b82f6;color:#1e40af;border-radius:4px;">Bezig met vertalen... Dit kan even duren.</div>';

      try {
        for (const lang of languages) {
          statusDiv.innerHTML = `<div style="padding:12px;background:#eff6ff;border-left:4px solid #3b82f6;color:#1e40af;border-radius:4px;">Vertalen naar ${AVAILABLE_LANGUAGES.find(l => l.code === lang)?.label || lang}...</div>`;

          const result = await api.translateDraft(activeDraftId, lang, translateImage);

          const overlay = submitBtn.closest('.modal-overlay');
          if (overlay) overlay.remove();

          openTranslationEditModal(result, lang);
          updateTranslationBadges();
          showAlert('Vertaling succesvol gegenereerd!', 'success');
        }
      } catch (error) {
        console.error('Translation error:', error);
        statusDiv.innerHTML = `<div style="padding:12px;background:#fef2f2;border-left:4px solid #ef4444;color:#991b1b;border-radius:4px;">Fout bij vertalen: ${escapeHtml(error.message)}</div>`;
        setButtonLoading(submitBtn, false);
      }
    });
  }
}

function openTranslationEditModal(translationResult, language) {
  const translated = translationResult.translated || {};
  const langInfo = AVAILABLE_LANGUAGES.find(l => l.code === language) || { label: language, flag: '' };

  let imagePreviewHtml = '';
  if (translationResult.translatedImage?.bytes_base64) {
    imagePreviewHtml = `
      <div style="margin-bottom:12px;">
        <label class="form-label">Vertaalde afbeelding</label>
        <img src="data:image/jpeg;base64,${translationResult.translatedImage.bytes_base64}"
             style="max-width:100%;border-radius:8px;border:1px solid #e0e0e0;" alt="Translated image" />
      </div>
    `;
  }

  const content = `
    <div style="display:flex;flex-direction:column;gap:12px;max-height:70vh;overflow-y:auto;">
      ${imagePreviewHtml}
      <div class="form-group">
        <label class="form-label">Titel</label>
        <input type="text" id="translation-edit-title" class="form-input" value="${escapeHtml(translated.title || '')}" />
      </div>
      <div class="form-group">
        <label class="form-label">Excerpt</label>
        <textarea id="translation-edit-excerpt" class="form-input" rows="2">${escapeHtml(translated.excerpt || '')}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Content (HTML)</label>
        <textarea id="translation-edit-content" class="form-input" rows="10">${escapeHtml(translated.contentHtml || '')}</textarea>
      </div>
      <details style="margin-top:4px;">
        <summary style="cursor:pointer;font-weight:600;color:#555;font-size:0.9rem;">SEO & Meta</summary>
        <div style="display:flex;flex-direction:column;gap:8px;margin-top:8px;">
          <div class="form-group">
            <label class="form-label">Slug</label>
            <input type="text" id="translation-edit-slug" class="form-input" value="${escapeHtml(translated.slug || '')}" />
          </div>
          <div class="form-group">
            <label class="form-label">Focus keyword</label>
            <input type="text" id="translation-edit-focuskw" class="form-input" value="${escapeHtml(translated.yoast?.focusKeyword || translated.yoast?.focuskw || '')}" />
          </div>
          <div class="form-group">
            <label class="form-label">Meta titel</label>
            <input type="text" id="translation-edit-metatitle" class="form-input" value="${escapeHtml(translated.yoast?.metaTitle || translated.yoast?.seo_title || '')}" />
          </div>
          <div class="form-group">
            <label class="form-label">Meta beschrijving</label>
            <textarea id="translation-edit-metadesc" class="form-input" rows="2">${escapeHtml(translated.yoast?.metaDescription || translated.yoast?.meta_desc || '')}</textarea>
          </div>
        </div>
      </details>
    </div>
  `;

  const footer = `
    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Sluiten</button>
    <button class="btn btn-primary" id="translation-save-btn">Vertaling opslaan</button>
  `;

  showModal(`${langInfo.flag} Vertaling: ${langInfo.label}`, content, footer);

  const saveBtn = document.getElementById('translation-save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const updatedTranslation = {
        ...translated,
        title: document.getElementById('translation-edit-title')?.value || translated.title,
        excerpt: document.getElementById('translation-edit-excerpt')?.value || translated.excerpt,
        contentHtml: document.getElementById('translation-edit-content')?.value || translated.contentHtml,
        slug: document.getElementById('translation-edit-slug')?.value || translated.slug,
        yoast: {
          ...(translated.yoast || {}),
          focusKeyword: document.getElementById('translation-edit-focuskw')?.value || translated.yoast?.focusKeyword,
          focuskw: document.getElementById('translation-edit-focuskw')?.value || translated.yoast?.focuskw,
          metaTitle: document.getElementById('translation-edit-metatitle')?.value || translated.yoast?.metaTitle,
          seo_title: document.getElementById('translation-edit-metatitle')?.value || translated.yoast?.seo_title,
          metaDescription: document.getElementById('translation-edit-metadesc')?.value || translated.yoast?.metaDescription,
          meta_desc: document.getElementById('translation-edit-metadesc')?.value || translated.yoast?.meta_desc,
        },
        language: language,
      };

      setButtonLoading(saveBtn, true);
      try {
        await api.updateDraftTranslation(activeDraftId, language, updatedTranslation);
        showAlert('Vertaling opgeslagen!', 'success');
        const overlay = saveBtn.closest('.modal-overlay');
        if (overlay) overlay.remove();
      } catch (error) {
        showAlert('Fout bij opslaan: ' + error.message, 'error');
        setButtonLoading(saveBtn, false);
      }
    });
  }
}

export async function updateTranslationBadges() {
  const badgeContainer = document.getElementById('translation-badges');
  if (!badgeContainer || !activeDraftId) return;

  try {
    const resp = await api.getDraftTranslations(activeDraftId);
    const translations = resp.translations || [];

    if (translations.length > 0) {
      badgeContainer.style.display = 'inline';
      badgeContainer.innerHTML = translations.map(t =>
        `<span class="badge badge-primary" style="margin-left:4px;font-size:0.7rem;padding:2px 6px;cursor:pointer;" data-lang="${t.language}" title="Klik om vertaling te bewerken">${t.language.toUpperCase()}</span>`
      ).join('');

      badgeContainer.querySelectorAll('[data-lang]').forEach(badge => {
        badge.addEventListener('click', async (e) => {
          e.stopPropagation();
          const lang = badge.getAttribute('data-lang');
          try {
            const translation = await api.getDraftTranslation(activeDraftId, lang);
            openTranslationEditModal({ translated: translation.translated }, lang);
          } catch (err) {
            showAlert('Fout bij laden vertaling: ' + err.message, 'error');
          }
        });
      });
    } else {
      badgeContainer.style.display = 'none';
      badgeContainer.innerHTML = '';
    }
  } catch (e) {
    console.error('Error updating translation badges:', e);
  }
}

window.openTranslateModal = openTranslateModal;
