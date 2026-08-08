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

  // Form Submit Handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const issue = issueInput.value.trim();
    const rounds = parseInt(roundsInput.value, 10);

    if (!issue) return;

    // Show Loading State
    submitBtn.disabled = true;
    btnText.textContent = "Negotiating...";
    btnSpinner.classList.remove("hidden");

    try {
      const response = await fetch("/negotiate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ issue, rounds })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      renderNegotiationResults(issue, data);
    } catch (err) {
      alert("Error initiating negotiation: " + err.message);
    } finally {
      submitBtn.disabled = false;
      btnText.textContent = "Initiate Negotiation";
      btnSpinner.classList.add("hidden");
    }
  });

  function renderNegotiationResults(issue, data) {
    emptyState.classList.add("hidden");
    outcomeCard.classList.remove("hidden");
    roundsContainer.innerHTML = "";

    const { rounds, outcome } = data;

    // Render Outcome Card
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

    // Update SVG progress ring
    const dashVal = Math.round(score * 100);
    scoreCircleProgress.setAttribute("stroke-dasharray", `${dashVal}, 100`);

    // Render Rounds Stream
    if (Array.isArray(rounds)) {
      rounds.forEach((r, idx) => {
        const roundCard = document.createElement("div");
        roundCard.className = "round-card";
        roundCard.style.animationDelay = `${idx * 0.15}s`;

        roundCard.innerHTML = `
          <div class="round-header">ROUND ${r.round}</div>
          
          <div class="turn-box turn-usa">
            <span class="avatar">🇺🇸</span>
            <div class="turn-content">
              <strong>USA Proposal</strong>
              <p>${escapeHtml(r.usa_proposal || "")}</p>
            </div>
          </div>

          <div class="turn-box turn-china">
            <span class="avatar">🇨🇳</span>
            <div class="turn-content">
              <strong>China Response</strong>
              <p>${escapeHtml(r.china_response || "")}</p>
            </div>
          </div>
        `;

        roundsContainer.appendChild(roundCard);
      });
    }
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
