/**
 * UI Utilities - Helper functions for UI interactions
 */

// Show alert/toast
export function showAlert(message, type = 'info', duration = 5000) {
  // Ensure toast container exists
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const alert = document.createElement('div');
  alert.className = `alert alert-${type} toast-slide-in`;
  alert.innerHTML = `
    <span>${escapeHtml(message)}</span>
    <button class="modal-close" onclick="this.parentElement.remove()">×</button>
  `;
  
  container.appendChild(alert);
  
  if (duration > 0) {
    setTimeout(() => {
      alert.classList.remove('toast-slide-in');
      alert.classList.add('toast-slide-out');
      setTimeout(() => alert.remove(), 300);
    }, duration);
  }
  
  return alert;
}

// Show modal
export function showModal(title, content, footer = null) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">${escapeHtml(title)}</h3>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
      </div>
      <div class="modal-body">
        ${content}
      </div>
      ${footer ? `<div class="modal-footer">${footer}</div>` : ''}
    </div>
  `;
  
  document.body.appendChild(overlay);
  overlay.classList.add('animate-fade-in');
  
  // Close on overlay click
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      overlay.remove();
    }
  });
  
  return overlay;
}

// Set button loading state
export function setButtonLoading(button, loading) {
  if (!button) {
    console.error('setButtonLoading called with null button');
    return;
  }
  
  if (loading) {
    if (button.classList.contains('btn-loading')) {
      return;
    }

    button.disabled = true;
    button.classList.add('btn-loading');
    button.dataset.originalHtml = button.innerHTML;
  } else {
    button.disabled = false;
    button.classList.remove('btn-loading');
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }
}

// Format date
export function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString('nl-NL', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Escape HTML
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Format job status
export function formatJobStatus(status) {
  const statusMap = {
    queued: { text: 'In Wachtrij', class: 'badge-primary' },
    running: { text: 'Bezig', class: 'badge-primary' },
    success: { text: 'Succesvol', class: 'badge-success' },
    partial_success: { text: 'Gedeeltelijk', class: 'badge-warning' },
    failed: { text: 'Gefaald', class: 'badge-error' },
  };
  
  const statusInfo = statusMap[status] || { text: status, class: 'badge-primary' };
  return `<span class="badge ${statusInfo.class}">${statusInfo.text}</span>`;
}
