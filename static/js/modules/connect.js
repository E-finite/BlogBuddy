/**
 * Connect Site module – WordPress site connection management.
 */

import { api } from '../api.js';
import { showAlert, setButtonLoading } from '../ui.js';

export function initConnectFallbackActions() {
  if (window.__connectFallbackActionsInitialized) {
    return;
  }
  window.__connectFallbackActionsInitialized = true;

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('#show-connect-form-btn');
    if (!trigger) {
      return;
    }

    const connectFormPanel = document.getElementById('connect-form-panel');
    if (!connectFormPanel) {
      return;
    }

    const connectorSitesPanel = document.getElementById('connector-sites-panel');
    const connectorSelect = document.getElementById('connectorType');
    const connectFormTitle = document.getElementById('connect-form-title');
    const connectFormDescription = document.getElementById('connect-form-description');
    const connectFormContext = document.getElementById('connect-form-context');
    const connectForm = document.getElementById('connect-site-form');
    const baseUrlInput = document.getElementById('wpBaseUrl');

    if (connectorSelect && !connectorSelect.value) {
      const hasWordPressOption = Array.from(connectorSelect.options || []).some((option) => option.value === 'wordpress');
      if (hasWordPressOption) {
        connectorSelect.value = 'wordpress';
      }
    }

    if (connectorSitesPanel) {
      connectorSitesPanel.classList.remove('hidden');
    }

    if (connectFormTitle) {
      connectFormTitle.textContent = 'Nieuwe WordPress Site Verbinden';
    }
    if (connectFormDescription) {
      connectFormDescription.textContent = 'Vul je WordPress-gegevens in om een nieuwe verbinding te maken.';
    }
    if (connectForm) {
      connectForm.reset();
    }

    if (connectFormContext) {
      connectFormContext.classList.remove('hidden');
      connectFormContext.classList.remove('alert-info');
      connectFormContext.classList.add('alert-warning');
      connectFormContext.innerHTML = '<span>Vul hieronder je WordPress verbinding in.</span>';
    }

    connectFormPanel.classList.remove('hidden');
    connectFormPanel.classList.remove('workspace-card-attention');
    void connectFormPanel.offsetWidth;
    connectFormPanel.classList.add('workspace-card-attention');
    connectFormPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });

    window.setTimeout(() => {
      if (baseUrlInput) {
        baseUrlInput.focus();
      }
    }, 130);

    window.setTimeout(() => {
      connectFormPanel.classList.remove('workspace-card-attention');
    }, 820);
  });
}

export function initConnectSite() {
  const form = document.getElementById('connect-site-form');
  const connectorSelect = document.getElementById('connectorType');
  const connectorSitesPanel = document.getElementById('connector-sites-panel');
  const connectedSitesList = document.getElementById('connected-sites-list');
  const showConnectFormBtn = document.getElementById('show-connect-form-btn');
  const connectFormPanel = document.getElementById('connect-form-panel');
  const connectFormTitle = document.getElementById('connect-form-title');
  const connectFormDescription = document.getElementById('connect-form-description');
  const connectFormContext = document.getElementById('connect-form-context');
  const baseUrlInput = document.getElementById('wpBaseUrl');
  const usernameInput = document.getElementById('wpUsername');
  const passwordInput = document.getElementById('wpApplicationPassword');
  if (!form) return;

  if (connectorSelect && !connectorSelect.value) {
    const hasWordPressOption = Array.from(connectorSelect.options || []).some((option) => option.value === 'wordpress');
    if (hasWordPressOption) {
      connectorSelect.value = 'wordpress';
    }
  }

  let connectedSites = [];

  function revealConnectForm(options = {}) {
    if (!connectFormPanel) {
      return;
    }

    const {
      focusInput = false,
      scrollToForm = false,
      emphasize = false
    } = options;

    connectFormPanel.classList.remove('hidden');

    if (emphasize) {
      connectFormPanel.classList.remove('workspace-card-attention');
      void connectFormPanel.offsetWidth;
      connectFormPanel.classList.add('workspace-card-attention');
      window.setTimeout(() => {
        connectFormPanel.classList.remove('workspace-card-attention');
      }, 780);
    }

    if (scrollToForm) {
      connectFormPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    if (focusInput && baseUrlInput) {
      window.setTimeout(() => {
        baseUrlInput.focus();
      }, 130);
    }
  }

  function renderConnectedSites() {
    if (!connectedSitesList) {
      return;
    }

    if (connectedSites.length === 0) {
      connectedSitesList.innerHTML = `
        <div class="connector-empty-state">
          Nog geen WordPress website verbonden. Kies hieronder voor een nieuwe verbinding om te starten.
        </div>
      `;
      return;
    }

    connectedSitesList.innerHTML = connectedSites.map((site) => `
      <button type="button" class="connector-site-button" data-site-id="${site.id}">
        <div class="connector-site-copy">
          <span class="connector-site-name">${site.wp_base_url}</span>
          <p class="connector-site-meta">Gebruiker: ${site.wp_username}</p>
        </div>
        <span class="badge badge-primary">Openen</span>
      </button>
    `).join('');
  }

  function showFormForSite(site = null, options = {}) {
    if (!connectFormPanel || !connectFormTitle || !connectFormDescription || !connectFormContext) {
      return;
    }

    const focusInput = Boolean(options.focusInput);
    const scrollToForm = Boolean(options.scrollToForm);
    const emphasize = Boolean(options.emphasize);

    if (site) {
      connectFormTitle.textContent = 'Verbonden WordPress Site';
      connectFormDescription.textContent = 'Werk deze verbinding bij of vervang ze met een nieuwe application password.';
      connectFormContext.classList.remove('hidden');
      connectFormContext.classList.remove('alert-warning');
      connectFormContext.classList.add('alert-info');
      connectFormContext.innerHTML = `
        <span>Je bekijkt de verbinding voor <strong>${site.wp_base_url}</strong>. Vul opnieuw een application password in om deze verbinding te updaten.</span>
      `;
      if (baseUrlInput) baseUrlInput.value = site.wp_base_url || '';
      if (usernameInput) usernameInput.value = site.wp_username || '';
      if (passwordInput) passwordInput.value = '';
    } else {
      connectFormTitle.textContent = 'Nieuwe WordPress Site Verbinden';
      connectFormDescription.textContent = 'Vul je WordPress-gegevens in om een nieuwe verbinding te maken.';
      form.reset();
      connectFormContext.classList.remove('hidden');
      connectFormContext.classList.remove('alert-info');
      connectFormContext.classList.add('alert-warning');
      connectFormContext.innerHTML = connectedSites.length > 0
        ? '<span>Je hebt al een WordPress site verbonden. Als je nu opslaat, wordt de bestaande verbinding vervangen.</span>'
        : '<span>Vul hieronder je eerste WordPress verbinding in.</span>';
    }

    revealConnectForm({
      focusInput,
      scrollToForm,
      emphasize
    });
  }

  async function loadConnectedSites() {
    if (!connectorSelect || connectorSelect.value !== 'wordpress') {
      if (connectorSitesPanel) connectorSitesPanel.classList.add('hidden');
      if (connectFormPanel) connectFormPanel.classList.add('hidden');
      return;
    }

    try {
      const sitesResponse = await api.getSites();
      connectedSites = Array.isArray(sitesResponse)
        ? sitesResponse
        : (Array.isArray(sitesResponse?.sites) ? sitesResponse.sites : []);

      renderConnectedSites();

      if (connectorSitesPanel) {
        connectorSitesPanel.classList.remove('hidden');
      }

      if (connectedSites.length === 0) {
        showFormForSite();
      }
    } catch (error) {
      console.error('Error loading connected sites:', error);
      connectedSites = [];
      if (connectedSitesList) {
        connectedSitesList.innerHTML = `
          <div class="connector-empty-state">
            Verbonden websites konden niet geladen worden. Probeer de pagina opnieuw te laden.
          </div>
        `;
      }
      if (connectorSitesPanel) {
        connectorSitesPanel.classList.remove('hidden');
      }

      showFormForSite();
    }
  }

  if (connectorSelect) {
    connectorSelect.addEventListener('change', async () => {
      await loadConnectedSites();
    });
  }

  if (connectedSitesList) {
    connectedSitesList.addEventListener('click', (event) => {
      const siteButton = event.target.closest('[data-site-id]');
      if (!siteButton) {
        return;
      }

      const selectedSite = connectedSites.find((site) => String(site.id) === String(siteButton.dataset.siteId));
      if (selectedSite) {
        showFormForSite(selectedSite);
      }
    });
  }

  if (showConnectFormBtn) {
    showConnectFormBtn.addEventListener('click', () => {
      showFormForSite(null, {
        focusInput: true,
        scrollToForm: true,
        emphasize: true
      });
    });
  }
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const formData = new FormData(form);
    const payload = {
      wpBaseUrl: formData.get('wpBaseUrl'),
      wpUsername: formData.get('wpUsername'),
      wpApplicationPassword: formData.get('wpApplicationPassword'),
    };
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.connectSite(
        payload.wpBaseUrl,
        payload.wpUsername,
        payload.wpApplicationPassword
      );
      
      if (result.replaced) {
        showAlert(`Site vervangen! Oude site (${result.oldSiteUrl}) is verwijderd en nieuwe site is verbonden.`, 'success', 8000);
      } else {
        showAlert(`Site verbonden! Site ID: ${result.siteId}`, 'success');
      }
      
      form.reset();
      
      await loadSitesDropdowns();
      await loadConnectedSites();
      
      sessionStorage.setItem('currentSiteId', result.siteId);

      const savedSite = connectedSites.find((site) => String(site.id) === String(result.siteId));
      showFormForSite(savedSite || null);
      
    } catch (error) {
      showAlert(error.message || 'Fout bij verbinden met WordPress', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });

  if (connectorSelect && connectorSelect.value === 'wordpress') {
    loadConnectedSites();
  }
}

export async function loadSitesDropdowns() {
  try {
    const response = await fetch('/api/sites');
    if (!response.ok) {
      console.error('Failed to load sites');
      return;
    }
    
    const sitesPayload = await response.json();
    const sites = Array.isArray(sitesPayload) ? sitesPayload : [];
    
    const siteIdSelect = document.getElementById('siteId');
    const pubSiteIdSelect = document.getElementById('pubSiteId');
    
    if (siteIdSelect) {
      siteIdSelect.innerHTML = '<option value="">-- Kies een site --</option>';
      sites.forEach(site => {
        const option = document.createElement('option');
        option.value = site.id;
        option.textContent = `${site.wp_base_url} (${site.wp_username})`;
        siteIdSelect.appendChild(option);
      });
    }
    
    if (pubSiteIdSelect) {
      pubSiteIdSelect.innerHTML = '<option value="">-- Kies een site --</option>';
      sites.forEach(site => {
        const option = document.createElement('option');
        option.value = site.id;
        option.textContent = `${site.wp_base_url} (${site.wp_username})`;
        pubSiteIdSelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error('Error loading sites:', error);
  }
}
