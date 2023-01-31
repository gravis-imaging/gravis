function setCookie(name,value,days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days*24*60*60*1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + value + expires + "; path=/";
}


function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();

            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));

                break;
            }
        }
    }

    return cookieValue;
}

window.csrftoken = getCookie('csrftoken');

function HSLToRGB (h, s, l) {
    s /= 100;
    l /= 100;
    const k = n => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = n =>
      l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return [255 * f(0), 255 * f(8), 255 * f(4)];
}

  
async function doJob(type, case_, params) {
    let start_result = await startJob(type, case_, params);
    console.log(`Do Job`,start_result.id);
    for (let i=0;i<100;i++) {
        let result = await getJob(type,start_result.id)
        if ( result["status"] == "Success" ) {
            return result;
        }
        await sleep(100);
    }
    return;
}


async function doFetch(url, body, method="POST") {
    let raw_result = await fetch(url, {
        method: method, 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        ...( method=="GET"? {} : {body: JSON.stringify(body)})
    })
    let text = await raw_result.text();
    
    try {
        return JSON.parse(text)
    } catch (e) {
        console.warn("Failed to parse as JSON", text);
        throw e
    }
}


async function startJob(type, case_, params) {
    var body = {
        case: case_,
        parameters: params,
    };
    var raw_result = await fetch(`/job/${type}`, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })
    try {
        return await raw_result.json()
    } catch (e) {
        console.warn("Failed to parse as JSON",raw_result)
        throw e
    }
    
}


function parseDicomTime(date, timestamp) {    
    const p = {
        year: parseInt(date.slice(0,4)),
        month: parseInt(date.slice(4,6))-1, // Javascript months are 0-indexed, DICOM months are 1-indexed
        day: parseInt(date.slice(6,8)),
        hour: parseInt(timestamp.slice(0,2)),
        minute: parseInt(timestamp.slice(2,4)),
        second: parseInt(timestamp.slice(4,6)),
        millisecond: 0
      };
    if (timestamp.length > 6) {
        p.millisecond = Math.round(1000*parseFloat(timestamp.slice(6)))
    }
    return new Date(p.year,p.month,p.day,p.hour,p.minute,p.second,p.millisecond)
}


async function getJob(job, id) {
    var result = await (await fetch(`/job/${job}?id=${id}`, {
        method: 'GET',   credentials: 'same-origin'
    })).json()
    return result
}


function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


function getJobInstances(result, case_id) {
    var urls = []
    for ( var instance of result["dicom_sets"][0] ) {
        urls.push("wadouri:" + 
        "/wado/" +case_id+
        '/studies/' +
        instance.study_uid +
        '/series/' +
        instance.series_uid +
        '/instances/' +
        instance.instance_uid +
        '/frames/1')
    };
    return urls;
}


const loadImage = async url => {
    const img = document.createElement('img')
    img.src = url
    return new Promise((resolve, reject) => {
      img.onload = () => resolve(img)
      img.onerror = reject
    })
  }

  async function viewportToImage(viewport) {
    const element = viewport.element.getElementsByTagName("svg")[0];
    const cloneElement = element.cloneNode(true);

    cloneElement.setAttribute("width", element.clientWidth);
    cloneElement.setAttribute("height", element.clientHeight);
    cloneElement.setAttribute("viewBox", `0 0 ${element.clientWidth} ${element.clientHeight}`)
    
    const pixelData = viewport.getCanvas().toDataURL("image/png");
    cloneElement.getElementsByTagName("defs")[0].insertAdjacentHTML("afterend",`<image x=0 y=0 width="100%" height=100% href="${pixelData}"></image>`)

    const svgAsXML = (new XMLSerializer()).serializeToString(cloneElement)
    const svgData = `data:image/svg+xml,${encodeURIComponent(svgAsXML)}`
    const img = await loadImage(svgData);
    const canvas = document.createElement('canvas');
    canvas.width = element.clientWidth;
    canvas.height = element.clientHeight;
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
    const dataURL = await canvas.toDataURL("image/png", 1.0);
    return dataURL;
}

export { setCookie, getCookie, HSLToRGB, doJob, doFetch, startJob, getJob, getJobInstances, viewportToImage };