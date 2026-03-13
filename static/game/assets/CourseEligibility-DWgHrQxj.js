import{r as p,E as S,j as e}from"./index-DRU2cTg1.js";import{s as ce,a as re}from"./firebase-Cuyihyr5.js";const C=t=>{if(!t)return null;try{const a=localStorage.getItem(`userData_${t}`);return a?JSON.parse(a):null}catch(a){return console.error("Error reading user data:",a),null}},_=(t,a)=>{if(!t){console.error("Phone number is required to save user data");return}try{const l={...C(t)||{},...a,lastUpdated:new Date().toISOString()};localStorage.setItem(`userData_${t}`,JSON.stringify(l))}catch(o){console.error("Error saving user data:",o)}},j=(t,a,o)=>{if(t)try{const r=(C(t)||{}).actions||[];r.push({action:a,data:o,timestamp:new Date().toISOString()}),_(t,{actions:r})}catch(l){console.error("Error tracking user action:",l)}},de=t=>C(t)||{},ue=t=>{if(!t)return!1;try{return C(t)?.eligibilityEmailSent===!0}catch(a){return console.error("Error checking eligibility email status:",a),!1}},pe=t=>{if(!t){console.error("Phone number is required to mark email as sent");return}try{_(t,{eligibilityEmailSent:!0,eligibilityEmailSentAt:new Date().toISOString()})}catch(a){console.error("Error marking eligibility email as sent:",a)}},k={to:"developer.topteen@gmail.com",from:"noreply@testprepgpt.ai"},V=async(t,a,o,l,r="")=>{if(!t)return{success:!1,message:"Recipient email address is required"};if(!a)return{success:!1,message:"Sender email address is required"};if(!o)return{success:!1,message:"Email subject is required"};if(!l&&!r)return{success:!1,message:"Email body (text or HTML) is required"};try{console.log("=== SENDING EMAIL VIA FIREBASE FUNCTION ==="),console.log("To:",t),console.log("From:",a),console.log("Subject:",o),console.log("=== END EMAIL DATA ===");const n=await ce({to:t,from:a,subject:o,text:l,html:r||l});return{success:n.success||!0,message:n.message||"Email sent successfully",messageId:n.messageId||`firebase-${Date.now()}`}}catch(n){return console.error("Error sending email:",n),console.log("=== EMAIL DATA (Error occurred) ==="),console.log("To:",t),console.log("From:",a),console.log("Subject:",o),console.log("=== END EMAIL DATA ==="),{success:!1,message:n.message||"Failed to send email via Firebase Function",error:n}}},me=t=>{const{phoneNumber:a,careerCluster:o,selectedStreams:l,winnerStream:r,educationInfo:n,course:x}=t,c=`
COURSE APPLICATION
==================

Phone Number: ${a||"N/A"}

Applied Course: ${x||"N/A"}

Career Information:
- Career Cluster: ${o||"N/A"}
- Selected Streams: ${l&&l.length>0?l.join(", "):"N/A"}
- Winner Stream: ${r||"N/A"}

Education Information:
- Background: ${n?.background||"N/A"}
- Stream: ${n?.stream||"N/A"}
- Specific Area: ${n?.specificArea||"N/A"}
- Study Location: ${n?.studyLocation||"N/A"}

---
Generated on: ${new Date().toLocaleString()}
  `.trim(),h=`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .course-highlight { background: white; padding: 15px; border-radius: 5px; margin-top: 10px; border-left: 4px solid #667eea; font-size: 16px; font-weight: bold; color: #667eea; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Course Application</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${a||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Applied Course</div>
        <div class="course-highlight">${x||"N/A"}</div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${o||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${l&&l.length>0?l.join(", "):"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${r||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${n?.background||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${n?.stream||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${n?.specificArea||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${n?.studyLocation||"N/A"}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();return{textBody:c,htmlBody:h}},he=t=>{const{phoneNumber:a,careerCluster:o,selectedStreams:l,winnerStream:r,educationInfo:n}=t,x=`
USER DETAILS FOR COUNSELLOR
===========================

Phone Number: ${a||"N/A"}

Career Information:
- Career Cluster: ${o||"N/A"}
- Selected Streams: ${l&&l.length>0?l.join(", "):"N/A"}
- Winner Stream: ${r||"N/A"}

Education Information:
- Background: ${n?.background||"N/A"}
- Stream: ${n?.stream||"N/A"}
- Specific Area: ${n?.specificArea||"N/A"}
- Study Location: ${n?.studyLocation||"N/A"}

---
Generated on: ${new Date().toLocaleString()}
  `.trim(),c=`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>User Details for Counsellor</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${a||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${o||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${l&&l.length>0?l.join(", "):"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${r||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${n?.background||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${n?.stream||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${n?.specificArea||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${n?.studyLocation||"N/A"}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();return{textBody:x,htmlBody:c}},ge=async t=>{try{const{textBody:a,htmlBody:o}=he(t),l=`User Eligibility Check - ${t.phoneNumber||"Unknown"}`,r=await V(k.to,k.from,l,a,o);return r.success?console.log("User data email sent successfully (silent)"):console.warn("Failed to send user data email (silent):",r.message),r}catch(a){return console.error("Error sending user data email (silent):",a),{success:!1,message:a.message}}},fe=async t=>{const{textBody:a,htmlBody:o}=me(t),l=`Course Application - ${t.course||"Unknown Course"} - ${t.phoneNumber||"Unknown"}`;return await V(k.to,k.from,l,a,o)};function be(){const t=document.cookie.match(/(^| )csrftoken=([^;]+)/);return t?t[2]:""}const ye=({winnerStream:t,fightResult:a,selectedStreams:o,selectedParameters:l,selectedCluster:r,onBack:n,onReset:x})=>{const[c,h]=p.useState(1),[d,U]=p.useState(null),[m,O]=p.useState(null),[g,B]=p.useState(null),[b,F]=p.useState(null),[E,X]=p.useState(null),[T,G]=p.useState(!1),[R,$]=p.useState(null),[Q,Y]=p.useState(!1),[I,A]=p.useState(null),[v,q]=p.useState(!1),[w,Z]=p.useState(!1),[M,ee]=p.useState(null),[se,z]=p.useState(!1);p.useEffect(()=>{fetch("/career-battle/api/eligibility-profile/",{credentials:"include"}).then(s=>s.json()).then(s=>{const i=s.profile||{};i.grade!=null&&i.grade!==""&&ee(String(i.grade).trim());let u=1,f=!1;i.education_background&&S[i.education_background]&&(U(i.education_background),u=2,f=!0);const N=i.education_background||"12th";i.stream&&S[N]?.streams?.includes(i.stream)&&(O(i.stream),u===2&&(u=3),f=!0);const L=i.stream&&S[N]?.specificAreas?.[i.stream];i.specific_area&&L&&L.includes(i.specific_area)&&(B(i.specific_area),u===3&&(u=4),f=!0),i.study_location&&(i.study_location==="India"||i.study_location==="Study Abroad")&&F(i.study_location),h(u),Z(f),q(!0)}).catch(()=>q(!0))},[]);const D=M!=null?parseInt(M,10):null,y=D==null||!Number.isNaN(D)&&D>=10,ie=s=>{const i=localStorage.getItem("userPhoneNumber");i&&j(i,"education_background_selected",{background:s}),U(s),h(2)},te=s=>{const i=localStorage.getItem("userPhoneNumber");i&&j(i,"education_stream_selected",{stream:s,background:d}),O(s),h(3)},ae=s=>{const i=localStorage.getItem("userPhoneNumber");i&&j(i,"specific_area_selected",{area:s,stream:m,background:d}),B(s)},W=s=>{const i=localStorage.getItem("userPhoneNumber");i&&j(i,"study_location_selected",{location:s}),F(s)},ne=async(s=!1)=>{if(!d||!m||!g||!b)return;const i=localStorage.getItem("userPhoneNumber");G(!0),$(null);try{s&&await fetch("/career-battle/api/eligibility-profile/",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","X-CSRFToken":be()},body:JSON.stringify({education_background:d,stream:m,specific_area:g,study_location:b})});const f=(await re({educationBackground:{background:d,stream:m,specificArea:g},winnerStream:t})).courses||[];X(f);const N={background:d,stream:m,specificArea:g,studyLocation:b};i&&(_(i,{educationInfo:N,courses:f,winnerStream:t,fightResult:a,selectedStreams:o,selectedParameters:l,selectedCluster:r}),j(i,"eligibility_checked",{courses:f,educationInfo:N}),ue(i)||ge({phoneNumber:i,careerCluster:r||null,selectedStreams:o||[],winnerStream:t||null,educationInfo:N}).then(P=>{P.success&&pe(i)}).catch(P=>console.error("Silent email error:",P))),h(5)}catch(u){console.error("Error checking course eligibility:",u),$(u.message||"Failed to check course eligibility. Please try again.")}finally{G(!1)}},le=()=>{if(!d||!m||!g||!b){$("Please complete all selections");return}z(!0)},J=s=>{z(!1),ne(s)},K=d&&m&&g&&b,oe=async s=>{const i=localStorage.getItem("userPhoneNumber");if(!i){alert("No user data found. Please login first.");return}A(s);try{const u=de(i),f={phoneNumber:i,careerCluster:r||null,selectedStreams:o||[],winnerStream:t||null,educationInfo:u.educationInfo||null,course:s},N=await fe(f);N.success?(Y(!0),j(i,"course_application",{course:s})):(alert(`Failed to send application: ${N.message}`),A(null))}catch(u){console.error("Error sending course application:",u),alert(`Error sending application: ${u.message}`),A(null)}},H=()=>{Y(!1),A(null),x?x():n&&n(),window.location.reload()};return e.jsxs("div",{className:"course-eligibility-container",role:"region","aria-labelledby":"course-eligibility-title",children:[e.jsxs("div",{className:"course-eligibility-header",children:[e.jsx("h1",{id:"course-eligibility-title",className:"course-eligibility-title",children:"Course Eligibility Check"}),e.jsxs("p",{className:"course-eligibility-subtitle",children:["Based on your education background and the winner stream: ",e.jsx("strong",{children:t})]})]}),v&&!y&&e.jsxs("div",{className:"eligibility-step eligibility-class-below-10",children:[e.jsx("p",{className:"step-title",children:"Course eligibility is for class 10 and above."}),e.jsx("p",{className:"eligibility-below-10-message",children:"Your current class doesn't require this step. You can still explore careers from the result screen."}),e.jsx("button",{type:"button",className:"back-button",onClick:n,children:"← Back to Result"})]}),v&&y&&c<5&&e.jsxs(e.Fragment,{children:[w&&c===4&&e.jsxs("div",{className:"eligibility-prefilled-summary",role:"status",children:[e.jsx("span",{className:"prefilled-label",children:"From your profile:"}),e.jsx("span",{className:"prefilled-value",children:d}),e.jsx("span",{className:"prefilled-sep",children:"→"}),e.jsx("span",{className:"prefilled-value",children:m}),e.jsx("span",{className:"prefilled-sep",children:"→"}),e.jsx("span",{className:"prefilled-value",children:g}),e.jsx("button",{type:"button",className:"prefilled-edit-link",onClick:()=>h(1),"aria-label":"Edit education details",children:"Edit"})]}),e.jsx("div",{className:`step-indicator ${w&&c===4?"step-indicator-minimal":""}`,children:w&&c===4?e.jsxs("div",{className:"step step-active",children:[e.jsx("span",{className:"step-number",children:"1"}),e.jsx("span",{className:"step-label",children:"Select study location"})]}):e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:`step ${c>=1?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"1"}),e.jsx("span",{className:"step-label",children:"Education"})]}),e.jsx("div",{className:`step-connector ${c>=2?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=2?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"2"}),e.jsx("span",{className:"step-label",children:"Stream"})]}),e.jsx("div",{className:`step-connector ${c>=3?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=3?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"3"}),e.jsx("span",{className:"step-label",children:"Area"})]}),e.jsx("div",{className:`step-connector ${c>=4?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=4?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"4"}),e.jsx("span",{className:"step-label",children:"Location"})]})]})})]}),!v&&c<5&&y&&e.jsx("div",{className:"eligibility-step eligibility-loading-step",children:e.jsx("p",{className:"step-title",children:"Loading your details…"})}),v&&y&&c===1&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Your Education Background"}),e.jsx("div",{className:"options-grid",children:Object.keys(S).map(s=>e.jsx("button",{className:`option-card ${d===s?"option-card-selected":""}`,onClick:()=>ie(s),"aria-pressed":d===s,children:e.jsx("span",{className:"option-name",children:s})},s))})]}),v&&y&&c===2&&d&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Your Stream"}),e.jsx("div",{className:"options-grid",children:S[d].streams.map(s=>e.jsx("button",{className:`option-card ${m===s?"option-card-selected":""}`,onClick:()=>te(s),"aria-pressed":m===s,children:e.jsx("span",{className:"option-name",children:s})},s))}),e.jsx("button",{className:"back-button",onClick:()=>h(1),children:"← Back"})]}),v&&y&&c===3&&d&&m&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Specific Area"}),e.jsx("div",{className:"options-grid",children:S[d].specificAreas[m].map(s=>e.jsx("button",{className:`option-card ${g===s?"option-card-selected":""}`,onClick:()=>ae(s),"aria-pressed":g===s,children:e.jsx("span",{className:"option-name",children:s})},s))}),e.jsxs("div",{className:"step-actions",children:[e.jsx("button",{className:"back-button",onClick:()=>h(2),children:"← Back"}),g&&e.jsx("button",{className:"continue-button",onClick:()=>h(4),children:"Continue →"})]})]}),v&&y&&c===4&&d&&m&&g&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Study Location"}),e.jsxs("div",{className:"options-grid",children:[e.jsx("button",{className:`option-card ${b==="India"?"option-card-selected":""}`,onClick:()=>W("India"),"aria-pressed":b==="India",children:e.jsx("span",{className:"option-name",children:"🇮🇳 India"})}),e.jsx("button",{className:`option-card ${b==="Study Abroad"?"option-card-selected":""}`,onClick:()=>W("Study Abroad"),"aria-pressed":b==="Study Abroad",children:e.jsx("span",{className:"option-name",children:"🌍 Study Abroad"})})]}),e.jsxs("div",{className:"step-actions",children:[e.jsx("button",{className:"back-button",onClick:()=>h(3),children:"← Back"}),e.jsx("button",{className:`check-button ${K?"check-button-active":"check-button-disabled"}`,onClick:le,disabled:!K||T,children:T?"Checking...":"Check Eligibility"})]})]}),R&&e.jsx("div",{className:"error-message",role:"alert",children:R}),c===5&&E&&e.jsxs("div",{className:"courses-results",children:[e.jsx("h2",{className:"results-title",children:"Eligible Courses"}),e.jsx("div",{className:"courses-list",children:E.length>0?e.jsx("ul",{className:"courses-ul",children:E.map((s,i)=>e.jsxs("li",{className:"course-item",children:[e.jsx("span",{className:"course-icon",children:"📚"}),e.jsx("span",{className:"course-name",children:s}),e.jsx("button",{className:"apply-button",onClick:()=>oe(s),disabled:I===s,children:I===s?"Sending...":"Apply"})]},i))}):e.jsx("p",{className:"no-courses",children:"No eligible courses found."})}),e.jsx("div",{className:"results-actions",children:e.jsx("button",{className:"back-button",onClick:n,children:"← Back to Game"})})]}),se&&e.jsx("div",{className:"success-popup-overlay eligibility-confirm-overlay",children:e.jsxs("div",{className:"success-popup eligibility-confirm-popup",onClick:s=>s.stopPropagation(),children:[e.jsx("h2",{className:"success-popup-title",children:"Update profile?"}),e.jsx("p",{className:"eligibility-confirm-message",children:"Save this education and stream info to your profile for next time?"}),e.jsxs("div",{className:"eligibility-confirm-buttons",children:[e.jsx("button",{type:"button",className:"eligibility-confirm-yes",onClick:()=>J(!0),children:"Yes"}),e.jsx("button",{type:"button",className:"eligibility-confirm-no",onClick:()=>J(!1),children:"No"})]})]})}),Q&&e.jsx("div",{className:"success-popup-overlay",onClick:H,children:e.jsxs("div",{className:"success-popup",onClick:s=>s.stopPropagation(),children:[e.jsx("div",{className:"success-popup-icon",children:"✅"}),e.jsx("h2",{className:"success-popup-title",children:"Thank You!"}),e.jsx("p",{className:"success-popup-message",children:"Our counsellor will contact you soon regarding your application for:"}),e.jsx("p",{className:"success-popup-course",children:I}),e.jsx("button",{className:"success-popup-button",onClick:H,children:"OK"})]})})]})};export{ye as default};
