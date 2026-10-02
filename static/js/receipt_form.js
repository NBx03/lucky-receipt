(function () {
  const form = document.getElementById("receipt-form");
  if (!form) return;

  const promoStart = form.dataset.promoStart; // ГГГГ-ММ-ДД
  const promoEnd = form.dataset.promoEnd;
  const minAmount = Number(form.dataset.minAmount);
  // «Сейчас» в часовом поясе акции на момент загрузки страницы. Время идёт только
  // вперёд, поэтому проверка «не в будущем» не отклонит корректную дату.
  const now = form.dataset.now; // ГГГГ-ММ-ДДTЧЧ:ММ

  const submitButton = form.querySelector('button[type="submit"]');
  const formError = document.getElementById("form-error");
  const formCard = document.getElementById("form-card");
  const success = document.getElementById("success");

  const REQUIRED = "Обязательное поле.";
  const formatDate = (iso) => iso.split("-").reverse().join(".");

  // Сообщения повторяют серверные: сервер остаётся источником истины.
  const validators = {
    fn: (value) =>
      !value ? REQUIRED : /^\d{16}$/.test(value) ? "" : "ФН состоит из 16 цифр.",
    fd: (value) =>
      !value ? REQUIRED : /^\d{1,10}$/.test(value) ? "" : "ФД состоит из 1–10 цифр.",
    fp: (value) =>
      !value ? REQUIRED : /^\d{1,10}$/.test(value) ? "" : "ФП состоит из 1–10 цифр.",
    purchased_at: (value) => {
      if (!value) return REQUIRED;
      const date = value.slice(0, 10);
      if (date < promoStart || date > promoEnd) {
        return `Дата покупки вне периода акции: с ${formatDate(promoStart)} по ${formatDate(promoEnd)}.`;
      }
      if (now && value > now) return "Дата покупки не может быть в будущем.";
      return "";
    },
    amount: (value) => {
      if (!value) return REQUIRED;
      const normalized = value.replace(/\s/g, "").replace(",", ".");
      if (!/^\d+(\.\d+)?$/.test(normalized)) {
        return "Введите сумму числом, например 1500.50.";
      }
      const [whole, fraction = ""] = normalized.split(".");
      if (fraction.length > 2) {
        return "Убедитесь, что вы ввели не более 2 цифр после запятой.";
      }
      if (whole.length + fraction.length > 10) {
        return "Убедитесь, что вы ввели не более 10 цифр.";
      }
      if (Number(normalized) < minAmount) {
        return `Сумма чека должна быть не меньше ${minAmount} ₽.`;
      }
      return "";
    },
  };

  const fieldBox = (name) => form.querySelector(`.field[data-field="${name}"]`);
  const inputOf = (name) => form.elements[name];

  function showError(name, message) {
    const box = fieldBox(name);
    if (!box) return false;
    const text = box.querySelector(".field__error");
    box.classList.add("field--error");
    text.textContent = `Ошибка! ${message}`;
    text.hidden = false;
    inputOf(name).setAttribute("aria-invalid", "true");
    return true;
  }

  function clearError(name) {
    const box = fieldBox(name);
    box.classList.remove("field--error");
    box.querySelector(".field__error").hidden = true;
    inputOf(name).removeAttribute("aria-invalid");
  }

  function showFormError(message) {
    formError.textContent = message;
    formError.hidden = false;
  }

  function validateField(name) {
    const message = validators[name](inputOf(name).value.trim());
    if (message) showError(name, message);
    else clearError(name);
    return !message;
  }

  Object.keys(validators).forEach((name) => {
    const input = inputOf(name);
    input.addEventListener("blur", () => {
      if (input.value.trim()) validateField(name);
    });
    input.addEventListener("input", () => {
      if (fieldBox(name).classList.contains("field--error")) clearError(name);
      formError.hidden = true;
    });
    fieldBox(name)
      .querySelector(".input__clear")
      .addEventListener("click", () => {
        input.value = "";
        clearError(name);
        input.focus();
      });
  });

  function showServerErrors(errors) {
    const general = [];
    Object.entries(errors).forEach(([name, messages]) => {
      const text = messages.join(" ");
      if (!(name in validators && showError(name, text))) general.push(text);
    });
    if (general.length) showFormError(general.join(" "));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    formError.hidden = true;

    const names = Object.keys(validators);
    const invalid = names.filter((name) => !validateField(name));
    if (invalid.length) {
      inputOf(invalid[0]).focus();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Отправка…";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (response.redirected) {
        // Сессия закончилась: сервер отправил на страницу входа.
        window.location.href = response.url;
        return;
      }
      if (response.status === 201) {
        formCard.hidden = true;
        success.hidden = false;
        success.querySelector("h1").tabIndex = -1;
        success.querySelector("h1").focus();
        return;
      }
      const data = await response.json().catch(() => null);
      if (response.status === 400 && data && data.errors) {
        showServerErrors(data.errors);
      } else {
        showFormError("Не удалось зарегистрировать чек. Обновите страницу и повторите.");
      }
    } catch (error) {
      showFormError("Нет связи с сервером. Проверьте соединение и повторите.");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Загрузить";
    }
  });
})();
