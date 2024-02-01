# Case browser

![image](site:images/case_browser.png)

<div class="grid" markdown>

| Tool        | Description                          |
| ----------- | ------------------------------------ |
| ![open](site:images/toolbar/open.png)       | Open case |
| ![unlock](site:images/toolbar/unlock.png)   | Set case status |
| ![process](site:images/toolbar/process.png) | Reprocess case |
| ![delete](site:images/toolbar/delete.png)   | Delete case |

| Tool        | Description                          |
| ----------- | ------------------------------------ |
| ![info](site:images/toolbar/info.png)       | Show info pane |
| ![tag](site:images/toolbar/tag.png)         | Update case tags |
| ![refresh](site:images/toolbar/refresh.png)   | Refresh |
| ![sort](site:images/toolbar/sort.png)       | Clear sort |
</div>

## Managing cases
Cases can have several statuses. 

<div class="grid" markdown>
| Status | Description |
| ------ | ----------- |
| Processing | Case is still processing |
| Ready | Ready for viewing |
| Viewing | Currently being viewed |
| Complete | Marked complete |
| Delete | Marked for deletion |
| Error | Error while processing |


``` mermaid
stateDiagram
    Processing --> Ready : complete
    Processing --> Error : error
    Ready --> Viewing : opened
    Viewing --> Complete : closed
    Viewing --> Ready : closed
    Complete --> Ready
    Complete --> Viewing
```
</div>

Processes first appear as "Processing." While processing, they can't be viewed other than by staff. If the processing fails, they are marked as "Error," and again are only viewable by staff accounts.

If a case is read-only or not in the "Viewing" state, this is displayed in the Viewer as one or more tags in the top bar:

![case status](site:images/case-status-tags.png)

## Opening, closing, and locking cases

Opening a "Ready" case updates the case to "Viewing." It also sets you as the case's current viewer. While you are viewing a case, other users can view but not edit it. The case will stay open until the user manually closes the case via the <button>:fontawesome-regular-rectangle-xmark: Close</button> button on the top bar. This will open a prompt to either reset the case back to Ready, or move it to Completed. Completed cases are read-only.

## Reopening completed cases

Users can reopen their own completed cases using the <button>:fontawesome-solid-lock-open: unlock</button> button on the Case Browser. Staff may reopen any case, even cases that they are not the current viewer for. 

