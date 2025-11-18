const introSection = document.querySelector(".introSection");
const stickyHeaderForMobile = document.querySelector(".stickyHeader");

const options = {
  root: null,
  threshold: 0,
};

const callback = function (entries) {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      stickyHeaderForMobile?.classList.add("hidden");
    } else {
      stickyHeaderForMobile?.classList.remove("hidden");
    }
  });
};

const Observer = new IntersectionObserver(callback, options);

Observer.observe(introSection);

