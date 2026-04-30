/**
 * Main Application Entry Point
 * 
 * Imports all feature modules and initializes them on DOMContentLoaded.
 */

import { api } from './api.js';
import { showAlert } from './ui.js';
import { initializeActiveDraftId } from './modules/state.js';
import { initConnectFallbackActions, initConnectSite, loadSitesDropdowns } from './modules/connect.js';
import { initGeneratePost } from './modules/generate.js';
import { initPublishPost } from './modules/publish.js';
import { initJobsView } from './modules/jobs.js';
import { initLinkLibrary } from './modules/links.js';
import { initBugReportModal } from './modules/bugreport.js';
import { checkUnseenChangelogs } from './modules/changelog.js';

function safeInit(name, fn) {
  try {
    const maybePromise = fn();
    if (maybePromise && typeof maybePromise.then === 'function') {
      maybePromise.catch((error) => {
        console.error(`[init:${name}]`, error);
      });
    }
  } catch (error) {
    console.error(`[init:${name}]`, error);
  }
}

async function checkHealth() {
  try {
    await api.health();
  } catch (error) {
    showAlert('API niet bereikbaar. Controleer of de server draait.', 'error', 0);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  safeInit('initializeActiveDraftId', initializeActiveDraftId);
  safeInit('initConnectFallbackActions', initConnectFallbackActions);
  safeInit('loadSitesDropdowns', loadSitesDropdowns);
  safeInit('initConnectSite', initConnectSite);
  safeInit('initGeneratePost', initGeneratePost);
  safeInit('initPublishPost', initPublishPost);
  safeInit('initJobsView', initJobsView);
  safeInit('initBugReportModal', initBugReportModal);
  safeInit('checkUnseenChangelogs', checkUnseenChangelogs);
  safeInit('initLinkLibrary', initLinkLibrary);
  safeInit('checkHealth', checkHealth);
});
