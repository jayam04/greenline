document.addEventListener("DOMContentLoaded", () => {
  // 1. Theme Management (Light / Dark)
  const themeToggle = document.getElementById("theme-toggle");
  const htmlEl = document.documentElement;

  const savedTheme = localStorage.getItem("greenline-showcase-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  
  if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
    htmlEl.setAttribute("data-theme", "dark");
  } else {
    htmlEl.setAttribute("data-theme", "light");
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const currentTheme = htmlEl.getAttribute("data-theme");
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      htmlEl.setAttribute("data-theme", nextTheme);
      localStorage.setItem("greenline-showcase-theme", nextTheme);
    });
  }

  // 2. Interactive Feature Tour Tabs
  const tabButtons = document.querySelectorAll(".tour-tab-btn");
  const tabPanels = document.querySelectorAll(".tour-panel");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");

      tabButtons.forEach((b) => b.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const activePanel = document.getElementById(targetId);
      if (activePanel) {
        activePanel.classList.add("active");
      }
    });
  });

  // 3. Lightbox Image Modal
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxCaption = document.getElementById("lightbox-caption");
  const lightboxClose = document.getElementById("lightbox-close");

  const zoomableImages = document.querySelectorAll("[data-zoomable]");

  zoomableImages.forEach((imgContainer) => {
    imgContainer.addEventListener("click", () => {
      const img = imgContainer.querySelector("img");
      if (img && lightbox && lightboxImg) {
        lightboxImg.src = img.src;
        lightboxImg.alt = img.alt || "Greenline Screenshot";
        if (lightboxCaption) {
          lightboxCaption.textContent = img.alt || "";
        }
        lightbox.classList.add("active");
        document.body.style.overflow = "hidden";
      }
    });
  });

  function closeLightbox() {
    if (lightbox) {
      lightbox.classList.remove("active");
      document.body.style.overflow = "";
    }
  }

  if (lightboxClose) {
    lightboxClose.addEventListener("click", closeLightbox);
  }

  if (lightbox) {
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) {
        closeLightbox();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeLightbox();
    }
  });

  // 4. Quickstart Copy Command
  const copyBtn = document.getElementById("copy-btn");
  const toast = document.getElementById("toast");

  function showToast(text) {
    if (!toast) return;
    toast.textContent = text;
    toast.style.display = "block";
    setTimeout(() => {
      toast.style.display = "none";
    }, 2500);
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const codeSnippet = document.getElementById("code-snippet");
      if (codeSnippet) {
        navigator.clipboard.writeText(codeSnippet.innerText.trim()).then(() => {
          showToast("Copied to clipboard! ✓");
        }).catch(() => {
          showToast("Failed to copy");
        });
      }
    });
  }
});
