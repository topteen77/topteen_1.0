const careerDeletePopUp = document.querySelector(".careerDeletePop");
const shortListedCareer = document.querySelectorAll(".shortlistedCareer");
const noDeleteCareer = document.querySelector(".noDeleteCareerBtn");
const yesDeleteCareer = document.querySelector(".yesDeleteCareerBtn")



shortListedCareer.forEach(elem => {
    const deleteBtn = elem.querySelector(".deleteCareer");
    deleteBtn.addEventListener("click", function(){
        console.log(this.dataset.id)
        const careerId = this.dataset.id;
        careerDeletePopUp.classList.remove("hidden");
        deleteFunction(careerId);
    })
})



function deleteFunction(name){
    noDeleteCareer.addEventListener("click", function(){
        careerDeletePopUp.classList.add("hidden")
    })
    yesDeleteCareer.addEventListener("click", function(){
        deletecareerinterest(name);
    })
}

