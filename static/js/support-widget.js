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

  function initWidget() {
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

      let waButtonHtml = "";
      if (role === "assistant" && /whatsapp/i.test(content)) {
        waButtonHtml = `
          <a href="${WHATSAPP_URL}" target="_blank" rel="noopener noreferrer" class="cl-chat-wa-pill">
            <svg viewBox="0 0 24 24">
              <path d="M12.031 6.172c-3.181 0-5.767 2.586-5.768 5.766-.001 1.298.38 2.27 1.019 3.287l-.711 2.598 2.664-.698c.974.532 1.839.814 2.802.814 3.182 0 5.768-2.587 5.769-5.766.001-3.182-2.585-5.769-5.768-5.769zm3.394 8.16c-.144.405-.837.774-1.17.824-.312.045-.634.072-1.854-.436-1.558-.648-2.55-2.228-2.628-2.332-.078-.104-.633-.843-.633-1.608 0-.765.399-1.141.541-1.296.142-.155.31-.194.414-.194.103 0 .207.001.298.006.096.005.225-.036.35.267.13.315.445 1.087.484 1.166.039.078.065.17.013.273-.052.104-.078.169-.155.26-.078.091-.164.202-.234.271-.078.078-.16.163-.069.319.091.156.403.666.865 1.077.595.53 1.096.695 1.252.773.155.078.247.065.337-.039.091-.104.389-.454.492-.61.104-.155.207-.13.35-.078.143.052.908.428 1.063.506.156.078.26.117.298.182.039.065.039.376-.105.781z"/>
            </svg>
            Escribir por WhatsApp
          </a>
        `;
      }

      msgDiv.innerHTML = `
        <div class="cl-chat-bubble">${escapeHtml(content)}</div>
        ${waButtonHtml}
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

        if (response.status === 429) {
          addMessageUI("assistant", "Has enviado demasiados mensajes seguidos. Por favor espera unos minutos o dale clic a 'Hablar con una persona' para WhatsApp.");
          return;
        }

        const data = await response.json();
        const reply = data.reply || "No fue posible procesar la respuesta. Por favor contáctanos por WhatsApp.";
        addMessageUI("assistant", reply);

        history.push({ role: "assistant", content: reply });
        if (history.length > 10) {
          history = history.slice(-10);
        }
      } catch (err) {
        removeTypingIndicator();
        addMessageUI("assistant", "Hubo un error de conexión al consultar el asistente. Puedes comunicarte directamente por WhatsApp.");
      } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWidget);
  } else {
    initWidget();
  }
})();
