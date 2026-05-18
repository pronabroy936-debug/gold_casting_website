window.addEventListener("load", () => {
  const loader = document.getElementById("page-loader");
  if (loader) loader.style.display = "none";
});

const menuToggle = document.getElementById("menuToggle");
const mobileNav = document.getElementById("mobileNav");

if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    mobileNav.classList.toggle("hidden");
  });
}

document.querySelectorAll(".gallery-thumb").forEach((thumb) => {
  thumb.addEventListener("click", () => {
    const image = document.getElementById("mainProductImage");
    if (!image) return;
    image.src = thumb.dataset.image;
    document.querySelectorAll(".gallery-thumb").forEach((item) => item.classList.remove("active"));
    thumb.classList.add("active");
  });
});
