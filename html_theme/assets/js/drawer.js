const drawerModal = document.querySelector(".drawerModal");
const drawerContent = document.querySelector(".drawerContent");
const drawerTrigger = document.querySelector(".drawerTrigger");
// const drawerCloser = document.querySelector(".drawerCloser");

const closeDrawer = function () {
  if (drawerModal) {
    drawerModal?.classList?.add("-translate-x-full");
  }
};

drawerTrigger?.addEventListener("click", function () {
  console.log(drawerContent);
  if (drawerModal) {
    drawerModal?.classList?.remove("-translate-x-full");
  }
});

drawerModal?.addEventListener("click", function (e) {
  const target = e.target;
  if (target.closest(".drawerCloser")) {
    closeDrawer();
    return;
  }
  const isContent = target?.closest(".drawerContent");
  if (isContent) return;
  closeDrawer();
});
