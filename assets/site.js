const canAnimate = window.matchMedia("(prefers-reduced-motion: no-preference)");

const portraitDialog = document.querySelector('.portrait-dialog');
const portraitTrigger = document.querySelector('.portrait-trigger');
const avatarGroup = document.querySelector('.avatar-group');
if (portraitDialog && portraitTrigger && typeof portraitDialog.showModal === 'function') {
  let previousOverflow = '';
  portraitTrigger.addEventListener('click', (event) => {
    event.preventDefault();
    avatarGroup.dataset.dismissed = 'true';
    previousOverflow = document.body.style.overflow;
    portraitDialog.showModal();
    document.body.style.overflow = 'hidden';
  });
  portraitDialog.querySelector('.portrait-close').addEventListener('click', () => portraitDialog.close());
  portraitDialog.addEventListener('click', (event) => {
    if (event.target !== portraitDialog) return;
    const r = portraitDialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) portraitDialog.close();
  });
  portraitDialog.addEventListener('close', () => {
    document.body.style.overflow = previousOverflow;
    portraitTrigger.focus({ preventScroll: true });
  });
  avatarGroup.addEventListener('pointerleave', () => { if (!portraitDialog.open) delete avatarGroup.dataset.dismissed; });
  avatarGroup.addEventListener('focusout', () => { if (!portraitDialog.open) delete avatarGroup.dataset.dismissed; });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') avatarGroup.dataset.dismissed = 'true'; });
}

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
