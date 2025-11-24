// app/static/custom.js

document.addEventListener("DOMContentLoaded", function () {
    const adminInput = document.getElementById("adminPassword");
    const clearBtn = document.getElementById("clearAdminPassword");

    const buttonsRequiringAdmin = document.querySelectorAll(".requires-admin");
    const hiddenPasswordFields = document.querySelectorAll("input.admin-password-field");

    function updateAdminState() {
        const pwd = adminInput ? adminInput.value.trim() : "";
        const enabled = pwd.length > 0;

        // Włącz/wyłącz przyciski wymagające hasła
        buttonsRequiringAdmin.forEach(btn => {
            btn.disabled = !enabled;
        });

        // Ustaw hasło w ukrytych polach
        hiddenPasswordFields.forEach(f => {
            f.value = pwd;
        });
    }

    if (adminInput) {
        adminInput.addEventListener("input", updateAdminState);
        adminInput.addEventListener("change", updateAdminState);
    }

    if (clearBtn && adminInput) {
        clearBtn.addEventListener("click", function () {
            adminInput.value = "";
            updateAdminState();
            adminInput.focus();
        });
    }

    // Inicjalizacja przy ładowaniu strony
    updateAdminState();
});
