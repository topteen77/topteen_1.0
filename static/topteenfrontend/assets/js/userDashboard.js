// const editTrigr = document.querySelector(".editTrigr");
// const editPop = document.querySelector(".editPop");

// document.addEventListener("click", function(e) {
//     console.log(editPop)
//     if (editTrigr.contains(e.target)) {
//         editPop.classList.remove("hidden");
//     } else {
//         editPop.classList.add("hidden")
//     }
// })

const drawerModal = document.querySelector(".drawerModal");
const drawerContent = document.querySelector(".drawerContent");
const drawerTrigger = document.querySelector(".drawerTrigger");


const clearFilter = document.querySelector(".clearFilter");

const toggleDirection = function(action){
    console.log(this)
    const direction = this?.dataset?.direction || "-translate-x-full";
    console.log(drawerModal)
  console.log(drawerContent);
  if (drawerModal) {
    console.log(action)
    if(action === "ADD"){
        drawerModal?.classList?.add(direction);
    }else{
        drawerModal?.classList?.remove(direction);
    }

  }
}

const closeDrawer = function () {
    toggleDirection.bind(this, "ADD")();
    console.log("Fd")
};

drawerTrigger?.addEventListener("click", function () {
 toggleDirection.bind(this, "REMOVE")();
});

drawerModal?.addEventListener("click", function (e) {
  const target = e.target;
  if (target.closest(".drawerCloser")) {
    closeDrawer();
    return;
  }
  const isContent = target?.closest(".drawerContent");
  if (isContent) return;
  const direction = this?.dataset?.direction || "-translate-x-full";
  console.log(direction)
  closeDrawer.bind(this)();
});

clearFilter?.addEventListener("click", function(){
  console.log(window.location.search)
  console.log(window.location.pathname)
  window.location.href=window.location.pathname
  
})