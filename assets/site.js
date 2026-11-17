const canAnimate = window.matchMedia("(prefers-reduced-motion: no-preference)");

if (canAnimate.matches && "IntersectionObserver" in window && "animate" in Element.prototype) {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;

      observer.unobserve(entry.target);
      if (!canAnimate.matches) continue;

      const animation = entry.target.animate(
        [{ opacity: 0.76, transform: "translateY(8px)" }, { opacity: 1, transform: "translateY(0)" }],
        { duration: 360, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
      );
      const stopForReducedMotion = ({ matches }) => {
        if (!matches) animation.cancel();
      };
      canAnimate.addEventListener("change", stopForReducedMotion);
      animation.finished.catch(() => {}).finally(() => {
        canAnimate.removeEventListener("change", stopForReducedMotion);
      });
    }
  }, { threshold: 0.25 });

  document.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
}
