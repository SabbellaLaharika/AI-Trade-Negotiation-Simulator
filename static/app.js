document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("negotiation-form");
  const issueInput = document.getElementById("issue");
  const roundsInput = document.getElementById("rounds");
  const roundsValSpan = document.getElementById("rounds-val");
  const submitBtn = document.getElementById("submit-btn");
  const btnText = document.getElementById("btn-text");
  const btnSpinner = document.getElementById("btn-spinner");

  const emptyState = document.getElementById("empty-state");
  const outcomeCard = document.getElementById("outcome-card");
  const outcomeStatusBadge = document.getElementById("outcome-status-badge");
  const outcomeIssueTitle = document.getElementById("outcome-issue-title");
  const scoreVal = document.getElementById("score-val");
  const scoreCircleProgress = document.getElementById("score-circle-progress");
  const finalTermsText = document.getElementById("final-terms-text");
  const roundsContainer = document.getElementById("rounds-container");

  const usaStancePreview = document.querySelector(".stance-usa small");
  const chinaStancePreview = document.querySelector(".stance-china small");

  // Fetch dynamic positions on page load
  fetchPositions();

  async function fetchPositions() {
    try {
      const res = await fetch("/positions");
      if (res.ok) {
        const data = await res.json();
        if (data.usa && data.usa.priorities && usaStancePreview) {
          usaStancePreview.textContent = data.usa.priorities.join(" • ");
        }
        if (data.china && data.china.priorities && chinaStancePreview) {
          chinaStancePreview.textContent = data.china.priorities.join(" • ");
        }
      }
    } catch (err) {
      console.warn("Could not fetch positions:", err);
    }
  }

  // Sync Rounds Slider value label
  roundsInput.addEventListener("input", () => {
    roundsValSpan.textContent = roundsInput.value;
  });

  // Preset topic tags click handler
  document.querySelectorAll(".preset-tag").forEach((tag) => {
    tag.addEventListener("click", (e) => {
      e.preventDefault();
      issueInput.value = tag.getAttribute("data-issue");
    });
  });

  // Form Submit Handler (Real-Time SSE Streaming)
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    const issue = issueInput.value.trim();
    const rounds = parseInt(roundsInput.value, 10);

    if (!issue) return;

    // Show Loading State
    submitBtn.disabled = true;
    btnText.textContent = "Negotiating...";
    btnSpinner.classList.remove("hidden");

    // Clear previous results & hide outcome until ready
    emptyState.classList.add("hidden");
    outcomeCard.classList.add("hidden");
    roundsContainer.innerHTML = "";

    const streamUrl = `/negotiate/stream?issue=${encodeURIComponent(issue)}&rounds=${rounds}`;
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "turn_start") {
          let roundCard = document.getElementById(`round-card-${data.round}`);
          if (!roundCard) {
            roundCard = document.createElement("div");
            roundCard.id = `round-card-${data.round}`;
            roundCard.className = "round-card";
            roundCard.innerHTML = `
              <div class="round-header">ROUND ${data.round}</div>
              
              <div class="turn-box turn-usa" id="turn-usa-${data.round}">
                <span class="avatar">🇺🇸</span>
                <div class="turn-content">
                  <strong>USA Proposal</strong>
                  <p class="turn-text" style="color: #94a3b8; font-style: italic;">Drafting proposal with Llama 3...</p>
                </div>
              </div>

              <div class="turn-box turn-china" id="turn-china-${data.round}">
                <span class="avatar">🇨🇳</span>
                <div class="turn-content">
                  <strong>China Response</strong>
                  <p class="turn-text" style="color: #64748b; font-style: italic;">Waiting for USA proposal...</p>
                </div>
              </div>
            `;
            roundsContainer.appendChild(roundCard);
            roundCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }

          if (data.agent === "china") {
            const chinaP = document.querySelector(`#turn-china-${data.round} .turn-text`);
            if (chinaP) {
              chinaP.textContent = "Reviewing USA terms and formulating counter-proposal...";
              chinaP.style.color = "#94a3b8";
            }
          }
        } else if (data.type === "proposal") {
          const usaP = document.querySelector(`#turn-usa-${data.round} .turn-text`);
          if (usaP) {
            usaP.textContent = data.text;
            usaP.style.color = "#e2e8f0";
            usaP.style.fontStyle = "normal";
          }
        } else if (data.type === "response") {
          const chinaP = document.querySelector(`#turn-china-${data.round} .turn-text`);
          if (chinaP) {
            chinaP.textContent = data.text;
            chinaP.style.color = "#e2e8f0";
            chinaP.style.fontStyle = "normal";
          }
        } else if (data.type === "outcome") {
          renderOutcomeCard(issue, data.outcome);
        } else if (data.type === "done") {
          eventSource.close();
          submitBtn.disabled = false;
          btnText.textContent = "Initiate Negotiation";
          btnSpinner.classList.add("hidden");
        }
      } catch (err) {
        console.error("Error processing stream event:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn("Stream connection closed or completed:", err);
      eventSource.close();
      submitBtn.disabled = false;
      btnText.textContent = "Initiate Negotiation";
      btnSpinner.classList.add("hidden");
    };
  });

  function renderOutcomeCard(issue, outcome) {
    outcomeCard.classList.remove("hidden");
    outcomeIssueTitle.textContent = issue;
    finalTermsText.textContent = outcome.final_terms;

    if (outcome.agreement_reached) {
      outcomeStatusBadge.textContent = "Agreement Reached";
      outcomeStatusBadge.className = "outcome-badge";
    } else {
      outcomeStatusBadge.textContent = "No Consensus Reached";
      outcomeStatusBadge.className = "outcome-badge failed";
    }

    const score = outcome.compromise_score || 0.0;
    scoreVal.textContent = score.toFixed(2);

    const dashVal = Math.round(score * 100);
    scoreCircleProgress.setAttribute("stroke-dasharray", `${dashVal}, 100`);

    outcomeCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
