/**
 * CruceLine — Asistente de IA (LLM Real en Español de Patio)
 * Widget flotante con soporte para historial de 10 mensajes y enlace a WhatsApp.
 */
(function() {
  const WHATSAPP_NUMBER = "52XXXXXXXXXX"; // Placeholder: Bruce coloca aquí el número real (ej. 528671234567)
  const WHATSAPP_URL = `https://wa.me/${WHATSAPP_NUMBER}?text=` + encodeURIComponent("Hola CruceLine, necesito hablar con una persona de soporte.");

  const origin = window.location.pathname.includes("landing") ? "landing" : "app";
  let history = []; // Últimos 10 mensajes [{role, content}]
  let isOpen = false;
  let initialized = false;

  function initWidget() {
    if (initialized) return;
    if (typeof state === "undefined" || !state || !state.user) {
      return;
    }
    initialized = true;

    // 1. Botón flotante para abrir el asistente
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "cl-chat-toggle";
    toggleBtn.setAttribute("aria-label", "Abrir Asistente CruceLine");
    toggleBtn.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M12 2C6.477 2 2 6.477 2 12c0 1.821.487 3.53 1.338 5L2.5 21.5l4.646-.827A9.957 9.957 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm1 14h-2v-2h2v2zm0-4h-2V7h2v5z"/>
      </svg>
      <span>Asistente CruceLine</span>
    `;

    // 2. Ventana de chat flotante
    const chatBox = document.createElement("div");
    chatBox.className = "cl-chat-box";
    chatBox.style.display = "none";
    chatBox.innerHTML = `
      <div class="cl-chat-header">
        <div class="cl-chat-header-title">
          <div class="cl-chat-avatar">CL</div>
          <div class="cl-chat-header-text">
            <h3><span class="cl-chat-status-dot"></span> Asistente CruceLine</h3>
            <p>Despacho y Cruces Fronterizos</p>
          </div>
        </div>
        <button class="cl-chat-close" title="Cerrar asistente">&times;</button>
      </div>

      <div class="cl-chat-messages" id="cl-messages-container">
        <div class="cl-chat-msg assistant">
          <div class="cl-chat-bubble">
            ¡Qué tal! Soy el asistente de CruceLine. Te ayudo con dudas de despacho, cruces por Comercio Mundial / Colombia, choferes o costos del piloto.
          </div>
          <span class="cl-chat-msg-time">Ahora</span>
        </div>
      </div>

      <form class="cl-chat-input-wrap" id="cl-chat-form">
        <input type="text" class="cl-chat-input" id="cl-chat-input" placeholder="Pregunta sobre puertos, tarifas, choferes..." autocomplete="off" />
        <button type="submit" class="cl-chat-send" id="cl-chat-send" title="Enviar mensaje">
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </form>
    `;

    document.body.appendChild(toggleBtn);
    document.body.appendChild(chatBox);

    const closeBtn = chatBox.querySelector(".cl-chat-close");
    const form = chatBox.querySelector("#cl-chat-form");
    const input = chatBox.querySelector("#cl-chat-input");
    const sendBtn = chatBox.querySelector("#cl-chat-send");
    const container = chatBox.querySelector("#cl-messages-container");

    function toggleChat(open) {
      isOpen = (open !== undefined) ? open : !isOpen;
      chatBox.style.display = isOpen ? "flex" : "none";
      if (isOpen) {
        input.focus();
        scrollToBottom();
      }
    }

    toggleBtn.addEventListener("click", () => toggleChat());
    closeBtn.addEventListener("click", () => toggleChat(false));

    function scrollToBottom() {
      container.scrollTop = container.scrollHeight;
    }

    function addMessageUI(role, content) {
      const msgDiv = document.createElement("div");
      msgDiv.className = `cl-chat-msg ${role}`;
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      msgDiv.innerHTML = `
        <div class="cl-chat-bubble">${escapeHtml(content)}</div>
        <span class="cl-chat-msg-time">${timeStr}</span>
      `;
      container.appendChild(msgDiv);
      scrollToBottom();
    }

    function showTypingIndicator() {
      const typingDiv = document.createElement("div");
      typingDiv.className = "cl-chat-typing";
      typingDiv.id = "cl-chat-typing-active";
      typingDiv.innerHTML = `
        <div class="cl-chat-typing-dot"></div>
        <div class="cl-chat-typing-dot"></div>
        <div class="cl-chat-typing-dot"></div>
      `;
      container.appendChild(typingDiv);
      scrollToBottom();
    }

    function removeTypingIndicator() {
      const ind = document.getElementById("cl-chat-typing-active");
      if (ind) ind.remove();
    }

    function escapeHtml(str) {
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    form.addEventListener("submit", async function(e) {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      // Agregar mensaje usuario al historial y a la UI
      input.value = "";
      addMessageUI("user", text);
      history.push({ role: "user", content: text });
      if (history.length > 10) {
        history = history.slice(-10);
      }

      input.disabled = true;
      sendBtn.disabled = true;
      showTypingIndicator();

      try {
        const response = await fetch("/api/soporte/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            messages: history,
            origen: origin
          })
        });

        removeTypingIndicator();

        if (response.status === 401) {
          addMessageUI("assistant", "Sesión no válida o expirada. Por favor recarga e inicia sesión.");
          return;
        }

        if (response.status === 429) {
          addMessageUI("assistant", "Has enviado demasiados mensajes seguidos. Por favor espera unos minutos antes de intentar de nuevo.");
          return;
        }

        const data = await response.json();
        const reply = data.reply || "No fue posible procesar la respuesta en este momento.";
        addMessageUI("assistant", reply);

        history.push({ role: "assistant", content: reply });
        if (history.length > 10) {
          history = history.slice(-10);
        }
      } catch (err) {
        removeTypingIndicator();
        addMessageUI("assistant", "Hubo un error de conexión al consultar el asistente. Intenta de nuevo más tarde.");
      } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
      }
    });
  }

  window.initSupportWidget = initWidget;

  // Si state ya está cargado con usuario autenticado (ej. script diferido)
  if (typeof state !== "undefined" && state && state.user) {
    initWidget();
  }
})();
