function showPopup(c) {
    document.getElementById("case_details_patient_name").innerText = c.patient_name;
    document.getElementById("case_details_mrn").innerText = c.mrn;
    document.getElementById("case_details_acc").innerText = c.acc;
    document.getElementById("case_details_num_spokes").innerText = c.num_spokes;
    document.getElementById("case_details_case_type").innerText = c.case_type;
    document.getElementById("case_details_exam_time").innerText = c.exam_time;
    document.getElementById("case_details_receive_time").innerText = c.receive_time;
    document.getElementById("case_details_status").innerText = c.status;
    document.getElementById("case_details_twix_id").innerText = c.twix_id;
    document.getElementById("case_details_case_location").innerText = c.case_location;
    document.getElementById("case_details_viewed_by_id").innerText = c.viewed_by_id;
    document.getElementById("case_details_last_read_by_id").innerText = c.last_read_by_id;
    document.getElementById("case_details_settings").innerText = JSON.stringify(c.settings, null, 4);
    
    const myModalEl = document.getElementById('modal');
    const modal = new mdb.Modal(myModalEl);
    modal.show();
}


export { showPopup };