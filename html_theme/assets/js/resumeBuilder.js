// Input Date placeholder
const dateInput = document.querySelectorAll(".dateInput");

dateInput.forEach(el => {
    el.addEventListener("focus", function(){
        this.type = 'date';
    })
    el.addEventListener("focusout", function(){
        this.type = 'text';
    })
})


// User Data Adding PopUps
const addDataBtns = document.querySelectorAll("[data-tab-target]");
const addDataContent = document.querySelectorAll("[data-tab-content]");
const addDataPopUp = document.querySelector(".addDataPop");

addDataBtns.forEach(elem => {
    elem.addEventListener("click", function(){
        const target = document.querySelector(elem.dataset.tabTarget);
        console.log(target);

        addDataContent.forEach(content => {
            content.classList.add("hidden");
        })

        addDataPopUp.classList.remove("hidden");
        target.classList.remove("hidden");
        document.body.style.overflow="hidden";

        // Close Button
        const xBtn = target.querySelector(".dataCloseBtn");
        xBtn.addEventListener("click", function(){
            target.classList.add("hidden")
            addDataPopUp.classList.add("hidden");
            document.body.style.overflow="auto";
        })

        // Done Button
        const doneBtn = target.querySelector(".dataDoneBtn");
        doneBtn.addEventListener("click", function(){
            target.classList.add("hidden")
            addDataPopUp.classList.add("hidden");
            document.body.style.overflow="auto";
        })
    })
})


// User data delete popUps
const deleteSec = document.querySelector(".deletePop");
const addedData = document.querySelectorAll(".addedData");
const noDelete = document.querySelector(".noDeleteBtn");
const yesDelete = document.querySelector(".yesDeleteBtn");


addedData.forEach(elem => {
    const deleteBtn = elem.querySelector(".dataDelete");
    deleteBtn.addEventListener("click", function(){
        deleteSec.classList.remove("hidden");
        const delMsg = deleteSec.querySelector(".deleteQuestn");
        document.body.style.overflow="hidden";
        
        const dataId = this.dataset.id;
        delMsg.textContent = `Are you sure you want delete ${dataId}?`
        deletingData(dataId);
    })
})

function deletingData(param){
    noDelete.addEventListener("click", function(){
        deleteSec.classList.add("hidden");
        document.body.style.overflow="auto";
    })
    yesDelete.addEventListener("click", function(){
        
    })

}