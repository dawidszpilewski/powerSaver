document.addEventListener("DOMContentLoaded", () => {
    const adminPasswordInput = document.getElementById("adminPasswordInput");
    const clearAdminPassword = document.getElementById("clearAdminPassword");
    const checkOnlineButton = document.getElementById("checkOnlineButton");
    const checkOnlineInfo = document.getElementById("checkOnlineInfo");

    let adminPassword = "";

    function syncAdminPasswordFields() {
        const hiddenFields = document.querySelectorAll(".admin-password-field");
        hiddenFields.forEach((el) => {
            el.value = adminPassword;
        });

        const adminRequiredButtons = document.querySelectorAll(".requires-admin");
        adminRequiredButtons.forEach((btn) => {
            btn.disabled = !adminPassword;
        });
    }

    // Zmiana hasła admina
    if (adminPasswordInput) {
        adminPasswordInput.addEventListener("input", () => {
            adminPassword = adminPasswordInput.value.trim();
            syncAdminPasswordFields();
        });
    }

    // Wyczyść hasło admina
    if (clearAdminPassword) {
        clearAdminPassword.addEventListener("click", () => {
            adminPassword = "";
            if (adminPasswordInput) {
                adminPasswordInput.value = "";
            }
            syncAdminPasswordFields();
        });
    }

    // Blokowanie przycisków wymagających hasła (gdyby ktoś próbował kliknąć bez)
    document.querySelectorAll(".requires-admin").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            if (!adminPassword) {
                e.preventDefault();
                alert("Podaj najpierw hasło administratora.");
            }
        });
    });

    // Obsługa przycisku "Sprawdź status online (ping)"
    if (checkOnlineButton) {
        checkOnlineButton.addEventListener("click", async () => {
            checkOnlineButton.disabled = true;
            checkOnlineInfo.textContent = "Sprawdzanie statusu online...";

            try {
                const resp = await fetch("/online-status");
                if (!resp.ok) {
                    throw new Error("Błąd odpowiedzi serwera");
                }
                const data = await resp.json();

                // Oczekujemy struktury: { results: [ {id, online}, ... ] }
                if (data && Array.isArray(data.results)) {
                    data.results.forEach((item) => {
                        const badge = document.querySelector(
                            `.online-badge[data-computer-id="${item.id}"]`
                        );
                        if (!badge) return;

                        // czyścimy klasy z poprzednich statusów
                        badge.classList.remove("bg-secondary", "bg-success", "bg-danger");

                        if (item.online) {
                            badge.classList.add("bg-success");
                            badge.textContent = "online";
                        } else {
                            badge.classList.add("bg-danger");
                            badge.textContent = "offline";
                        }
                    });

                    checkOnlineInfo.textContent = "Statusy zaktualizowane.";
                } else {
                    checkOnlineInfo.textContent = "Nieprawidłowa odpowiedź serwera.";
                }
            } catch (err) {
                console.error(err);
                checkOnlineInfo.textContent = "Błąd podczas sprawdzania statusu online.";
            } finally {
                setTimeout(() => {
                    checkOnlineButton.disabled = false;
                }, 1000);
            }
        });
    }

    // Logika dla pola "Wyjątek" – przycisk aktywny dopiero po 2 słowach
    document.querySelectorAll(".exclusion-user-input").forEach((input) => {
        const form = input.closest("form");
        if (!form) return;
        const button = form.querySelector(".exclusion-button");
        if (!button) return;

        function updateButtonState() {
            const value = input.value.trim();
            const words = value.split(/\s+/).filter(Boolean);
            const hasTwoWords = words.length >= 2;
            const hasAdmin = !!adminPassword;

            button.disabled = !(hasTwoWords && hasAdmin);
        }

        input.addEventListener("input", updateButtonState);
        // pierwsze wywołanie przy starcie
        updateButtonState();
    });
});
