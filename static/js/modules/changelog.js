/**
 * Changelog module – unseen changelog popup.
 */

import { api } from '../api.js';

export async function checkUnseenChangelogs() {
  const overlay = document.getElementById('changelog-overlay');
  if (!overlay) return;

  let changelogs;
  try {
    const data = await api.getUnseenChangelogs();
    changelogs = data.changelogs || [];
  } catch {
    return;
  }

  if (!changelogs.length) return;

  const latest = changelogs[0];
  const allIds = changelogs.map(c => c.id);

  document.getElementById('changelog-version').textContent = latest.version;
  document.getElementById('changelog-title').textContent = latest.title;
  document.getElementById('changelog-body').innerHTML = latest.content_html;

  setTimeout(() => {
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }, 600);

  const closeAndDismiss = async () => {
    overlay.classList.remove('active');
    document.body.style.overflow = '';
    for (const id of allIds) {
      try { await api.dismissChangelog(id); } catch { /* ignore */ }
    }
  };

  document.getElementById('changelog-close').onclick = closeAndDismiss;
  document.getElementById('changelog-dismiss').onclick = closeAndDismiss;
  overlay.onclick = (e) => { if (e.target === overlay) closeAndDismiss(); };
}
