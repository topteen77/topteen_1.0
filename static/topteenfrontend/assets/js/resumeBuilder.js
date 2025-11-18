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
// console.log(addDataPopUp)

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

            const inputList = target.querySelectorAll('input[type="text"], input[type="date"], select, textarea');
            const result=[...inputList].every(popUpFormCheck);

            if(result){
                target.classList.add("hidden");
                addDataPopUp.classList.add("hidden");
                document.body.style.overflow="auto";
                fireAlert("Details saved successfully!", "success");
            }else{
                console.log("Incomplete")
            }
    })
})

})

function popUpFormCheck(el){
    return el.value;
}


// User data delete popUps
const deleteSec = document.querySelector(".deletePop");
const addedData = document.querySelectorAll(".addedData");
const noDelete = document.querySelector(".noDeleteBtn");
const yesDelete = document.querySelector(".yesDeleteBtn");


function deletingData(dataId,dataUrl,datamdivid,dataddivid){
    noDelete.addEventListener("click", function(){
        deleteSec.classList.add("hidden");
        document.body.style.overflow="auto";
    })
    yesDelete.addEventListener("click", function(){
        deleteResumeAttr(dataId,dataUrl,datamdivid,dataddivid)
    })
}

// Onclick Function for deletion
function addedDeleteHandler(param){
    deleteSec.classList.remove("hidden");
    const delMsg = deleteSec.querySelector(".deleteQuestn");
    document.body.style.overflow="hidden";
    
    const dataId = param.dataset.id;
    const dataMsg = param.dataset.title;
    const dataUrl = param.dataset.url;
    const dataddivid  = param.dataset.ddivid;
    const datamdivid  = param.dataset.mdivid;
    delMsg.textContent = `Are you sure you want delete ${dataMsg}?`
    deletingData(dataId,dataUrl,datamdivid,dataddivid);
}


function closeModelYesNo(){
    deleteSec.classList.add("hidden");
    document.body.style.overflow="auto";
}

function deleteResumeAttr(dataId,url,mdivid,ddivid){
    var form = document.createElement("form");
    form.setAttribute("method","POST");
    var hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", 'csrfmiddlewaretoken');
    hiddenField.setAttribute("value", csrf);
    form.appendChild(hiddenField);
    var hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "text");
    hiddenField.setAttribute("name","id");
    hiddenField.setAttribute("value",dataId);
    form.appendChild(hiddenField);
     var formData = new FormData(form);
    $.ajax({
        url: url,
        type: 'POST',
        data: formData,
        success: function (data) {
            $(document.getElementById(ddivid)).html(data.htmld);
            $(document.getElementById(mdivid)).html(data.htmlm);
            closeModelYesNo()
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    });
}



$('#aboutformsubmit').on('click',function(e){
    e.preventDefault();    
    var formData = new FormData(document.getElementById("aboutform"));

    var about = formData.get("about").trim();

    if ( about ) {
    $.ajax({
        url: resumeabout,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#aboutd').html(data.htmld);
            $('#aboutm').html(data.htmlm);
            document.getElementById("aboutform").reset();
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    }); 
    } else {
        document.getElementById("abouterrortag").textContent = "This field is required"; 
        fireAlert('All Fields are required',"error");
    }   
});

function validDateFormData(formData){
    for (const pair of formData.entries()) {
        // console.log(`${pair[0]}, ${pair[1]}`);
        if (formData.get(pair[0]).trim() == ""){
            document.getElementById(pair[0]+"errortag").textContent = "This field is required"; 
        }
    }
}

function clearAllErrorTag(){
    const errorTag = document.querySelectorAll(".errortag");
    errorTag.forEach(erl => {
        erl.textContent="";
    })
}

$('#skillformsubmit').on('click',function(e){
    e.preventDefault(); 
    clearAllErrorTag()   
    var formData = new FormData(document.getElementById("skillform"));

    if ( formData.get("skilltitle").trim() && formData.get("skilldesc").trim() && formData.get("skillprofficiency") ) {
    $.ajax({
        url: resumeskill,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#skilld').html(data.htmld);
            $('#skillm').html(data.htmlm);
            document.getElementById("skillform").reset();
            document.getElementById("skillcount").textContent="Skills"+" "+"("+data.count+")";
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    }); 
    } else {
        validDateFormData(formData);
        if (formData.get("skillprofficiency") == null){
            document.getElementById("skillprofficiencyerrortag").textContent = "Please select profficiency";
        }
        fireAlert('All Fields are required',"error");
    }     
});

$('#certificateformsubmit').on('click',function(e){
    e.preventDefault();    
    clearAllErrorTag()  
    var formData = new FormData(document.getElementById("certificateform"));

    if ( formData.get("certificatetitle").trim() && formData.get("certificatedescription").trim() && formData.get("issuedate") ) {
    $.ajax({
        url: resumecertificate,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#certificated').html(data.htmld);
            $('#certificatem').html(data.htmlm);
            document.getElementById("certificateform").reset();
            document.getElementById("certificatecount").textContent="Certifications"+" "+"("+data.count+")";
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    });  
    } else {
        validDateFormData(formData);
        fireAlert('All Fields are required',"error");
    }   
});

$('#internshipformsubmit').on('click',function(e){
    
    e.preventDefault();
    clearAllErrorTag()      
    var formData = new FormData(document.getElementById("internshipform"));

    if ( formData.get("provider").trim() && formData.get("internshipdescription").trim() && formData.get("role").trim() && formData.get("start_date") && formData.get("end_date")) {
    $.ajax({
        url: resumeinternship,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#internshipm').html(data.htmlm);
            $('#internshipd').html(data.htmld);
            document.getElementById("internshipform").reset();
            document.getElementById("internshipcount").textContent="Internships"+" "+"("+data.count+")";
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    });  
    } else {
        validDateFormData(formData);
        fireAlert('All Fields are required',"error");
    }   
});

$('#activityformsubmit').on('click',function(e){
    e.preventDefault();  
    clearAllErrorTag()    
    var formData = new FormData(document.getElementById("activityform"));

    if ( formData.get("activity").trim() && formData.get("activity_description").trim() && formData.get("particiopation_date") ) {
    $.ajax({
        url: resumeactivity,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#activityd').html(data.htmld);
            $('#activitym').html(data.htmlm);
            document.getElementById("activityform").reset();
            document.getElementById("activitycount").textContent="Extracurricular Activitie"+" "+"("+data.count+")";
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    }); 
    } else {
        validDateFormData(formData);
        fireAlert('All Fields are required',"error");
    }     
});

$('#volunteerformsubmit').on('click',function(e){
    e.preventDefault();  
    clearAllErrorTag()    
    var formData = new FormData(document.getElementById("volunteerform"));

    if ( formData.get("volunteertitle").trim() && formData.get("volunteerrole").trim() && formData.get("volunteerdescription").trim() && formData.get("volunteer_start_date") && formData.get("volunteer_end_date")) {
    $.ajax({
        url: resumevolunteer,
        type: 'POST',
        data: formData,
        success: function (data) {
            $('#volunteerd').html(data.htmld);
            $('#volunteerm').html(data.htmlm);
            document.getElementById("volunteerform").reset()
            document.getElementById("volunteercount").textContent="Volunteering"+" "+"("+data.count+")";
        },
        error: function(jqXHR, textStatus, errorThrown) {
            fireAlert(jqXHR.responseJSON.message,"error");
        },
        error: function(xhr, status, error) {
            console.log(xhr);
            if (xhr == 'undefined' || xhr == undefined) {
                fireAlert(error,"error");
            } else {
                fireAlert(jqXHR.responseJSON.message,"error");
            }
        },
        cache: false,
        contentType: false,
        processData: false
    });   
    } else {
        validDateFormData(formData);
        fireAlert('All Fields are required',"error");
    }  
});
