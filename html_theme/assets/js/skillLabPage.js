const videoPlayer = document.querySelector(".videoPlayer");
const stickyDiv = document.querySelector(".stickyDiv");

const callback = function (entries) {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      stickyDiv.classList.add("hidden");
    } else {
      stickyDiv.classList.remove("hidden");
    }
  });
};

const options = {
  root: null,
  threshold: [0],
  rootMargin: "10px",
};
const observer = new IntersectionObserver(callback, options);

observer.observe(videoPlayer);
