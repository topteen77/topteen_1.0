const modal = document.querySelector(".modal");
const modalContent = document.querySelector(".modalContent");
const modalTriggers = document.querySelectorAll(".modalTrigger");
const modalCloser = document.querySelector(".modalCloser");
const closeModal = function () {
  if (modal) {
    modal?.classList?.add("hideModal");
  }
};
modalTriggers?.forEach((modalTrigger) => {
  modalTrigger?.addEventListener("click", function (e) {
    e.preventDefault();
    if (modal) {
      modal?.classList?.remove("hideModal");
    }
  });
});

modal?.addEventListener("click", function (e) {
  const target = e.target;
  if (target.closest(".modalCloser")) {
    closeModal();
    return;
  }
  const isContent = target?.closest(".modalContent");
  if (isContent) return;
  closeModal();
});

modalCloser?.addEventListener;
