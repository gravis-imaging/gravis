To transfer cases from Yarra, configure a mode to use the `SFTPTransfer` module. 

The value of `case_type` in `gravis_settings` will determine how the case will be processed.

```
[Transfer]
Bin1=%bd/SFTPTransfer
Args1=%mc %td %rit

[sftp_transfer]
TargetHost=<gravis server hostname>
TargetUser=gravis
TargetPath=/opt/gravis/data/incoming

[gravis_settings]
case_type=<GRASP Onco or GRASP MRA>
```