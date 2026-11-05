const navOpen = document.querySelector(".mobile-open-btn");
const navClose = document.querySelector(".mobile-close-btn");
const primaryNavigation = document.getElementById("primary-navigation");

function setNavigationState(isOpen) {
  if (!primaryNavigation) return;

  primaryNavigation.setAttribute("data-visible", isOpen ? "true" : "false");

  if (navClose) {
    navClose.setAttribute("data-visible", isOpen ? "true" : "false");
  }

  document.body.style.overflow = isOpen ? "hidden" : "";
}

if (navOpen && primaryNavigation) {
  navOpen.addEventListener(
    "click",
    () => {
      const isOpen = primaryNavigation.getAttribute("data-visible") === "true";
      setNavigationState(!isOpen);
    },
    { passive: true }
  );
}

if (navClose && primaryNavigation) {
  navClose.addEventListener(
    "click",
    () => {
      setNavigationState(false);
    },
    { passive: true }
  );
}

if (primaryNavigation) {
  primaryNavigation.addEventListener(
    "click",
    (event) => {
      if (event.target.closest("a")) {
        setNavigationState(false);
      }
    },
    { passive: true }
  );
}

window.addEventListener("resize", () => {
  if (window.innerWidth > 760) {
    document.body.style.overflow = "";
  }
});
