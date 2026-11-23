/**
 * LearnSphere - Client Interactivity & Async AJAX Engine
 */

// Toast notification utility
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  let icon = "fa-info-circle";
  if (type === "success") icon = "fa-check-circle";
  if (type === "error") icon = "fa-exclamation-circle";

  toast.innerHTML = `
    <div style="display:flex; align-items:center; gap:0.6rem;">
      <i class="fas ${icon}" style="color:${type==='success'?'#10b981':'#6366f1'}"></i>
      <span>${message}</span>
    </div>
    <button onclick="this.parentElement.remove()" style="background:none; border:none; color:#64748b; cursor:pointer;">&times;</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(50px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// CSRF Token Helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Copy Code to Clipboard
function copyCode(btn, codeText) {
  navigator.clipboard.writeText(codeText).then(() => {
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
    btn.style.background = "#10b981";
    btn.style.color = "#fff";
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.style.background = "";
      btn.style.color = "";
    }, 2000);
    showToast("Snippet copied to clipboard!", "success");
  }).catch(() => {
    showToast("Failed to copy code snippet.", "error");
  });
}

// Toggle Resource Bookmark
async function toggleBookmark(resourceId, btnElement) {
  try {
    const csrfToken = getCookie("csrftoken");
    const response = await fetch(`/resources/api/${resourceId}/bookmark/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest"
      }
    });

    if (response.status === 401) {
      window.location.href = `/auth/login/?next=${window.location.pathname}`;
      return;
    }

    const data = await response.json();
    if (data.status === "success") {
      const isBookmarked = data.data.bookmarked;
      if (btnElement) {
        const icon = btnElement.querySelector("i");
        if (icon) {
          if (isBookmarked) {
            icon.className = "fas fa-bookmark";
            btnElement.classList.add("active");
            showToast("Resource added to your bookmarks!", "success");
          } else {
            icon.className = "far fa-bookmark";
            btnElement.classList.remove("active");
            showToast("Resource removed from bookmarks.");
          }
        }
      }
    }
  } catch (err) {
    showToast("Network error updating bookmark.", "error");
  }
}

// Toggle Project Upvote
async function toggleUpvote(projectId, btnElement) {
  try {
    const csrfToken = getCookie("csrftoken");
    const response = await fetch(`/innovation/api/${projectId}/upvote/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest"
      }
    });

    if (response.status === 401) {
      window.location.href = `/auth/login/?next=${window.location.pathname}`;
      return;
    }

    const data = await response.json();
    if (data.status === "success") {
      const upvoted = data.data.upvoted;
      const count = data.data.count;
      if (btnElement) {
        const countSpan = btnElement.querySelector(".upvote-count");
        if (countSpan) countSpan.textContent = count;
        if (upvoted) {
          btnElement.classList.add("btn-primary");
          btnElement.classList.remove("btn-secondary");
          showToast("Upvoted! Thank you for supporting student innovation.", "success");
        } else {
          btnElement.classList.remove("btn-primary");
          btnElement.classList.add("btn-secondary");
          showToast("Upvote removed.");
        }
      }
    }
  } catch (err) {
    showToast("Error updating upvote.", "error");
  }
}

// Enroll in Smart Education Course
async function enrollCourse(courseId, btnElement) {
  try {
    const csrfToken = getCookie("csrftoken");
    const response = await fetch(`/courses/api/${courseId}/enroll/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest"
      }
    });

    if (response.status === 401) {
      window.location.href = `/auth/login/?next=${window.location.pathname}`;
      return;
    }

    const data = await response.json();
    if (data.status === "success") {
      if (btnElement) {
        btnElement.innerHTML = '<i class="fas fa-check-circle"></i> Enrolled';
        btnElement.className = "btn btn-emerald btn-sm";
        btnElement.disabled = true;
      }
      showToast("Enrolled successfully! Track your progress in Dashboard.", "success");
    } else {
      showToast(data.message || "Enrollment failed.", "error");
    }
  } catch (err) {
    showToast("Error processing course enrollment.", "error");
  }
}

// Modal management
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("active");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("active");
}

// Submit Project Modal Form
document.addEventListener("DOMContentLoaded", () => {
  const submitProjectForm = document.getElementById("submit-project-form");
  if (submitProjectForm) {
    submitProjectForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(submitProjectForm);
      const payload = {
        title: formData.get("title"),
        category: formData.get("category"),
        abstract: formData.get("abstract"),
        tech_stack: formData.get("tech_stack"),
        repo_url: formData.get("repo_url"),
        demo_url: formData.get("demo_url"),
      };

      try {
        const csrfToken = getCookie("csrftoken");
        const res = await fetch("/innovation/api/submit/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest"
          },
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.status === "success") {
          showToast("Project published successfully!", "success");
          closeModal("project-modal");
          setTimeout(() => window.location.reload(), 1000);
        } else {
          showToast(result.message || "Failed to submit project.", "error");
        }
      } catch (err) {
        showToast("Network error submitting project.", "error");
      }
    });
  }

  // Initialize Ambient Sparkle Canvas & Scroll Sequencer
  initSparkleCanvas();
  initScrollSequencer();
});

// ==========================================
// Ambient Sparkling Canvas & Animation Engine
// ==========================================
let sparklesActive = true;
let sparkleAnimationId = null;

function initSparkleCanvas() {
  const canvas = document.getElementById("sparkle-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReduced) {
    canvas.style.display = "none";
    sparklesActive = false;
    return;
  }

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  window.addEventListener("resize", () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const colors = ["#4285f4", "#ea4335", "#fbbc05", "#34a853", "#9334e6"];
  const particles = [];
  const maxParticles = Math.min(45, Math.floor(width / 35));

  for (let i = 0; i < maxParticles; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 3.5 + 2,
      color: colors[Math.floor(Math.random() * colors.length)],
      alpha: Math.random() * 0.6 + 0.2,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      twinkleSpeed: Math.random() * 0.03 + 0.01,
      twinkleDir: 1
    });
  }

  // Draw 4-point Google sparkle star
  function drawSparkle(x, y, size, color, alpha) {
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
    ctx.fillStyle = color;
    ctx.beginPath();
    const r = size * 2.2;
    ctx.moveTo(x, y - r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.quadraticCurveTo(x, y, x, y + r);
    ctx.quadraticCurveTo(x, y, x - r, y);
    ctx.quadraticCurveTo(x, y, x, y - r);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function loop() {
    if (!sparklesActive) return;
    ctx.clearRect(0, 0, width, height);

    for (let p of particles) {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;

      p.alpha += p.twinkleSpeed * p.twinkleDir;
      if (p.alpha > 0.8) {
        p.alpha = 0.8;
        p.twinkleDir = -1;
      } else if (p.alpha < 0.15) {
        p.alpha = 0.15;
        p.twinkleDir = 1;
      }

      drawSparkle(p.x, p.y, p.size, p.color, p.alpha);
    }

    sparkleAnimationId = requestAnimationFrame(loop);
  }

  loop();
}

function toggleSparkles() {
  sparklesActive = !sparklesActive;
  const btn = document.getElementById("sparkle-toggle-btn");
  const canvas = document.getElementById("sparkle-canvas");
  if (sparklesActive) {
    if (canvas) canvas.style.display = "block";
    initSparkleCanvas();
    if (btn) btn.innerHTML = '<i class="fas fa-sparkles"></i> Sparkles: On';
    showToast("Ambient sparkle animation active", "info");
  } else {
    if (sparkleAnimationId) cancelAnimationFrame(sparkleAnimationId);
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      canvas.style.display = "none";
    }
    if (btn) btn.innerHTML = '<i class="far fa-eye-slash"></i> Sparkles: Paused';
    showToast("Sparkle animation paused", "info");
  }
}

// ==========================================
// Scroll-Driven Vertical Sequencer Engine
// ==========================================
function initScrollSequencer() {
  const steps = document.querySelectorAll(".sequencer-step");
  const panels = document.querySelectorAll(".sequencer-panel");
  if (!steps.length || !panels.length) return;

  const observerOptions = {
    root: null,
    rootMargin: "-25% 0px -35% 0px",
    threshold: 0.2
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const stepIndex = entry.target.getAttribute("data-step");
        activateSequencerStep(stepIndex);
      }
    });
  }, observerOptions);

  steps.forEach((step) => observer.observe(step));
}

function activateSequencerStep(stepIndex) {
  const steps = document.querySelectorAll(".sequencer-step");
  const panels = document.querySelectorAll(".sequencer-panel");

  steps.forEach((step) => {
    if (step.getAttribute("data-step") === stepIndex) {
      step.classList.add("active");
    } else {
      step.classList.remove("active");
    }
  });

  panels.forEach((panel) => {
    if (panel.getAttribute("data-panel") === stepIndex) {
      panel.classList.add("active");
    } else {
      panel.classList.remove("active");
    }
  });
}

// ==========================================
// Category Switcher Tabs & Accessible Playback
// ==========================================
function switchCategoryTab(tabId, btn) {
  document.querySelectorAll(".category-content-panel").forEach((el) => (el.style.display = "none"));
  document.querySelectorAll(".category-tab-btn").forEach((b) => {
    b.classList.remove("active");
    b.setAttribute("aria-selected", "false");
  });

  const target = document.getElementById("category-panel-" + tabId);
  if (target) target.style.display = "block";

  btn.classList.add("active");
  btn.setAttribute("aria-selected", "true");
}

let isDemoPlaying = true;
function toggleDemoPlayback(btn) {
  isDemoPlaying = !isDemoPlaying;
  const loopBars = document.querySelectorAll(".looping-progress-bar");
  if (btn) {
    btn.setAttribute("aria-pressed", String(!isDemoPlaying));
    if (isDemoPlaying) {
      btn.innerHTML = '<i class="fas fa-pause"></i> Pause Preview';
      loopBars.forEach((b) => (b.style.animationPlayState = "running"));
      showToast("Interactive demo resumed");
    } else {
      btn.innerHTML = '<i class="fas fa-play"></i> Play Preview';
      loopBars.forEach((b) => (b.style.animationPlayState = "paused"));
      showToast("Interactive demo paused");
    }
  }
}
