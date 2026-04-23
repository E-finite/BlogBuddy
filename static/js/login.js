(function () {
  "use strict";

  const adminSelector = document.getElementById("admin-company-selector");
  const adminCompanyInput = document.getElementById("admin_company_id");

  if (!adminSelector) {
    return;
  }

  let adminModeEnabled = false;

  function setAdminModeVisibility(isVisible) {
    adminModeEnabled = isVisible;
    adminSelector.classList.toggle("is-visible", isVisible);

    if (isVisible && adminCompanyInput) {
      adminCompanyInput.focus();
    }
  }

  document.addEventListener("keydown", function (event) {
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "a") {
      event.preventDefault();
      setAdminModeVisibility(!adminModeEnabled);
    }
  });

  if (window.location.search.includes("admin=1")) {
    setAdminModeVisibility(true);
  }
})();