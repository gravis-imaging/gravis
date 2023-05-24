function debounce(delay, callback) {
    let timeout
    return (...args) => {
        clearTimeout(timeout)
        timeout = setTimeout(() => {
            callback(...args)
        }, delay)
    }
}

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

  
async function doJob(type, case_, params, force=false) {
    let start_result = await startJob(type, case_, params, force);
    console.log(`Do Job`,start_result.id);
    for (let i=0;i<100;i++) {
        let result = await getJob(type,start_result.id)
        if ( result["status"] == "SUCCESS" ) {
            return result;
        }
        if ( result["status"] == "FAILED" ) {
            throw Error("Failed")
        }
        await sleep(100);
    }
    return;
}


async function doFetch(url, body={}, method="POST") {
    const response = await fetch(url, {
        method: method, 
        credentials: 'same-origin',        
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        ...( method=="GET"? {} : {body: JSON.stringify(body)})
    })
    if (!response.ok) {
        throw new Error(response.statusText)
    }

    const text = await response.text();
    if (text.length == 0) {
        return text
    }
    try {
        return JSON.parse(text)
    } catch (e) {
        console.warn("Failed to parse as JSON", text);
        throw e
    }
}


async function startJob(type, case_, params, force=false) {
    var body = {
        case: case_,
        parameters: params,
        force: force
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

async function loadVolumeWithRetry(volume) {
    for ( let i=0;i<2;i++) {
        const load_result = await new Promise( resolve => {
            volume.load( e => resolve(e) );
        });
        if ( load_result.framesLoaded == load_result.numFrames ) {
            return true;
        }
        console.error("Detected error during volume loading.");
        volume.loadStatus.loaded = false;
    }

    errorToast('Error while loading volume, some slices may be missing.');

    return false;
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


async function encodeSVG(svg_xml, width, height) {
    const svgData = `data:image/svg+xml,${encodeURIComponent(svg_xml)}`
    const img = await loadImage(svgData);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
    return await canvas.toDataURL("image/png", 1.0);
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

    return await encodeSVG(svgAsXML, element.clientWidth*2, element.clientHeight*2)
}
function viewportInVolume(viewport) {
    const imageData = viewport.getDefaultImageData();
    return cornerstone.utilities.indexWithinDimensions(
        cornerstone.utilities.transformWorldToIndex(imageData,
            viewport.getCamera().focalPoint),imageData.getDimensions()
    )
}

function fixUpCrosshairs(toolGroup="STACK_TOOL_GROUP_MAIN") {
    // Sometimes the crosshairs gets out of sync with the actual cameras. 
    // Not sure if this is a bug in Cornerstone or our own code, but this recalculates the 
    const mainTools = cornerstone.tools.ToolGroupManager.getToolGroup(toolGroup);
    const crosshairsInstance = mainTools.getToolInstance(cornerstone.tools.CrosshairsTool.toolName);
    crosshairsInstance.computeToolCenter(crosshairsInstance._getViewportsInfo());
}

async function chartToImage(chart) {
    const graphWidth = parseFloat(chart.graphDiv.style.width);
    const legendWidth = 200;
    const totalWidth = graphWidth + legendWidth;
    const height = parseFloat(chart.graphDiv.style.height);
    
    let svgString = `<svg width="${totalWidth}" height="${height}" viewBox="0 0 ${totalWidth} ${height}" xmlns="http://www.w3.org/2000/svg">
<style>
text {
    font-size: 14px;
    font-family:"Roboto",sans-serif;
    fill: white;
}
</style>
<rect width="100%" height="100%" fill="black" />`

    const canvases = chart.graphDiv.getElementsByTagName("canvas");
    for (const c of canvases) {
        const pixelData = c.toDataURL("image/png");
        svgString += `<image x="0" y="0" width="${graphWidth}" height="${height}" href="${pixelData}"></image>`
    }
    const labels = chart.graphDiv.getElementsByClassName("dygraph-axis-label")
    for (const label of labels) {
        const text = label.textContent 
        const parentStyle = label.parentElement.style;
        const x = parseFloat(parentStyle.left);
        const y = parseFloat(parentStyle.top);
        const width = parseFloat(parentStyle.width);
        if (label.classList.contains("dygraph-axis-label-y")) { // It's a y-axis label
            // "hanging" baseline ends up aligning them right.
            svgString += `<text x="${x + width}px" y="${y}px" text-anchor="end" dominant-baseline="hanging">${text}</text>`
        } else if (label.classList.contains("dygraph-axis-label-x")) { // It's an x-axis label
            if (parentStyle.textAlign == "center") {
                svgString += `<text x="${x + width/2.0}px" y="${y}px" dominant-baseline="hanging" text-anchor="middle">${text}</text>`
            } else if (parentStyle.textAlign == "right") {
                svgString += `<text x="${x + width}px" y="${y}px" dominant-baseline="hanging" text-anchor="end">${text}</text>`
            } else {
                svgString += `<text x="${x}px" y="${y}px" text-anchor="start">${text}</text>`
            }
        }
    }

    const legend_entries = chart.graphDiv.getElementsByClassName("dygraph-legend")[0].children
    let y = 7;
    let x = 2;
    for( const entry of legend_entries ) {
        let text,color;
        let b = entry.getElementsByTagName("b")[0];
        if (b) {
             // This happens when a timepoint is selected
            let span = b.getElementsByTagName("span")[0]
            text = span.innerText;
            color = span.style.color;
        } else {
            text = entry.innerText;
            color = entry.style.color;    
        }
        svgString += `<line x1="${graphWidth+x}px" y1="${y}px" x2="${graphWidth+x+20}" y2="${y}px" stroke-width="2" stroke="${color}" />`
        svgString += `<text x="${graphWidth+x+22}px" y="${y}px" dominant-baseline="central" text-anchor="start" font-weight="bold" style="fill:${color};">${text}</text>`
        // Arrange into several columns.
        if (y > height-15) {
            y = 7;
            x += 75;
        } else {
            y += 15;
        }
    }
    svgString += "</svg>"
    console.log(svgString);

    return await encodeSVG(svgString, totalWidth*2, height*2)
    // const svgData = `data:image/svg+xml,${encodeURIComponent(svgString)}`
    // const img = await loadImage(svgData);
    // const canvas = document.createElement('canvas');
    // canvas.width = totalWidth*2;
    // canvas.height = height*2;
    // canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
    // const dataURL = await canvas.toDataURL("image/png", 1.0);
    // console.log(img,canvas)
    // return dataURL;
}


class Vector {
    static sub(arr_a,arr_b) {
        let r = Array(arr_a.length);
        for (let i=0;i<arr_a.length;i++) 
            r[i] = arr_a[i] - arr_b[i];
        return r;
    }
    static add(arr_a,arr_b) {
        let r = Array(arr_a.length);
        for (let i=0;i<arr_a.length;i++) 
            r[i] = arr_a[i] + arr_b[i];
        return r;
    }
    static mul(arr_a,k) {
        let r = Array(arr_a.length);
        for (let i=0;i<arr_a.length;i++) 
            r[i] = arr_a[i] * k;
        return r;
    }
    static len(arr_a){
        return Math.sqrt(arr_a.reduce((p, n) => p+n*n,0));
    }
    static dot(arr_a, arr_b) {
        let r = 0;
        for (let i=0;i<arr_a.length;i++) 
            r += arr_a[i] * arr_b[i];
        return r;
    }
    static avg(arr){    
        return Vector.mul(arr.reduce(Vector.add, [0,0,0]), 1/arr.length);
    }
    static eq(arr_a,arr_b) {
        if (arr_a.length != arr_b.length) return false;
        for (let i=0;i<arr_a.length;i++){
            if (arr_a[i] != arr_b[i]) return false;
        }
        return true;
    }
}


const scrollViewportToPoint = (viewport, centerPoint, noEvent=false, fixCrosshairs=true) => {
    let cam = viewport.getCamera();
    const moveAmount = Vector.dot(cam.viewPlaneNormal, centerPoint) - Vector.dot(cam.viewPlaneNormal, cam.focalPoint)
    const delta = Vector.mul(cam.viewPlaneNormal, moveAmount);    
    cam = {...cam, 
                focalPoint: Vector.add(cam.focalPoint, delta),
                position: Vector.add(cam.position,delta)
            }
    // TODO: this doesn't work and ends up desyncing the viewports. 
    // } else if ( mode == "center") {
    // const offset = Vector.sub(cam.position, cam.focalPoint);
    // cam = {...cam, 
    //             focalPoint: centerPoint,
    //             position: Vector.add(centerPoint,offset)
    //         }
    // }
    if (noEvent){
        viewport.setCameraNoEvent(cam);
    } else {
        viewport.setCamera(cam);
    }
    if (fixCrosshairs) {
        fixUpCrosshairs();
    }
    viewport.render()
}

function decacheVolumes() {
    // This preemptively boots volumes if the cache is getting too large. 
    // Struggled to reliably recover from a full-cache situation; this tries to always leave headroom. 
    // Additionally, and very puzzlingly, catching CACHE_SIZE_EXCEEDED errors seems to only sort of work, 
    // in that catching it doesn't prevent the error showing up in the console. 
    const volumeIterator = cornerstone.cache._volumeCache.keys();

    const maxCacheSize = cornerstone.cache.getMaxCacheSize();
    while ( cornerstone.cache.getCacheSize() / maxCacheSize > 0.8 ) {
        const { value: volumeId, done } = volumeIterator.next();
        if (done) {
            break;
        }
        console.warn("Decaching volumes...", volumeId);
        cornerstone.cache.removeVolumeLoadObject(volumeId);
        cornerstone.triggerEvent(cornerstone.eventTarget, cornerstone.Enums.Events.VOLUME_CACHE_VOLUME_REMOVED, {
            volumeId,
        });
    }
}
function download(file) {
    const link = document.createElement('a');
    const url = URL.createObjectURL(file);
    
    link.href = url;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

const CommonSwal = Swal.mixin({
    showClass: {
        backdrop: 'swal2-noanimation',
        popup: '',
    },
    hideClass: {
        popup: '',
    },
})

async function confirmPrompt(text, title="Are you sure?", preConfirm=null) {
    let extra = {}
    if (preConfirm) {
        extra = {
            preConfirm: preConfirm,
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading()
        }
    }
    return await CommonSwal.fire({
        title: title,
        text: text,  
        icon: "question",
        iconColor: "#FFF",
        showCancelButton: true,
        confirmButtonColor: "#1266f1",
        cancelButtonColor: "#d33",
        confirmButtonText: "Yes",
        ...extra,
    })
}

async function errorPrompt(text,title="Error") {
    return await CommonSwal.fire({
        icon: "error",
        title: title,
        iconColor: "#FFF",
        html: `<p>${text}</p>`
    })
}

async function infoPrompt(text,title="Information") {
    return await CommonSwal.fire({
        icon: "info",
        title: title,
        text: text,
        iconColor: "#FFF"
    })
}

async function successPrompt(text, title="Success") {
    return await CommonSwal.fire({
        icon: "success",
        title: title,
        text: text,
        iconColor: "#FFF"
    })
}

async function inputPrompt(label, title, placeholder, value) {
    return await CommonSwal.fire({
        input: "text",
        inputTitle: title,
        inputLabel: label,
        inputPlaceholder: placeholder || "",
        inputValue: value,
        showCancelButton: true,
    })
}

const ToastSwal = CommonSwal.mixin({
    toast: true,
    position: 'bottom-right',
    customClass: {
        popup: 'colored-toast'
    },
    timer: 3000,
    showConfirmButton: false,
    showClass: {
        backdrop: 'swal2-noanimation', // disable backdrop animation
        popup: '',                     // disable popup animation
    },        
})
async function errorToast(title) {
    ToastSwal.fire({
        icon: 'error',
        iconColor: 'red',
        title: title,
    });
}
async function successToast(title) {
    ToastSwal.fire({
        icon: 'info',
        iconColor: 'green',
        title: title,
    });
}
export { debounce, setCookie, download, getCookie, HSLToRGB, doJob, doFetch, viewportInVolume, loadVolumeWithRetry, startJob, getJob, getJobInstances, viewportToImage, scrollViewportToPoint, fixUpCrosshairs, Vector, chartToImage, decacheVolumes, confirmPrompt, inputPrompt, errorPrompt, errorToast, successPrompt,infoPrompt, successToast };
