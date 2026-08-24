# 5G-Shark: Registration Reject Log Directory

## Overview
This directory contains raw, parsed signaling logs (`OP_A_Reject.txt`) demonstrating the consequences of Registration Rejects injected by the 5G-Shark Fake Base Station (FBS) against a Samsung S23 User Equipment (UE) that was initially connected to a commercial 5G SA network. 

The captures document Uplink and Downlink RRC/NAS messages. The primary focus of these logs is to observe the UE's behavior and state transitions when subjected to various NAS rejection causes injected by the FBS.

> **Data Privacy Notice:** All critical and personally identifiable network data (including SUPI/IMSI, PLMN, Cell IDs, etc.) within the `.txt` file have been strictly anonymized to protect the network operator and the user's SIM. The logical sequence and protocol structures remain fully intact for analysis.

---

## How to Read the Log File
The entries in `OP_A_Reject.txt` follow a structured timeline of events. To assist in parsing the traces, follow these steps:

### 1. Locate the Reject Cause
First, navigate to the specific cause section. These are demarcated in the file with headers. For example:
> `############################ Cause: 6 (Illegal ME) ##############################`

### 2. Identify the Radio Access Technology (RAT)
Next, identify the release version of the message. Note that while the 3GPP Technical Specification (TS) version might change between messages, the **Release (Rel)** number reliably indicates the network type (RAT):

* **5G SA:** Look for `3GPP TS 24.501` [...] `Rel 16`
* **5G NSA/LTE:** Look for `3GPP TS 24.301` [...] `Rel 15`
* **UMTS (3G):** Look for `3GPP TS 25.331` [...] `Rel 11`

### 3. Key Messages to Analyze
Depending on the identified Release/RAT, you will encounter the following critical RRC and NAS messages:

**5G SA (Rel 16)**
* **SIB1 (RRC):** System Information Block Type 1, broadcasting cell access parameters.
* **REGISTRATION REQUEST (NAS):** The UE attempting to register with the network.
* **REGISTRATION REJECT (NAS):** The malicious rejection from the FBS containing the attack "Cause".
* **IDENTITY RESPONSE (NAS):** The UE's response to an identity request (monitor this for the IMSI Null scheme).
* **PDU SESSION ESTABLISHMENT REQUEST (NAS):** The UE requesting a user-plane data connection.

**LTE / 5G NSA (Rel 15)**
* **ATTACH REQUEST (NAS):** The UE attempting to attach to the 4G core network.
* **TRACKING AREA UPDATE (TAU) REQUEST (NAS):** The UE notifying the network that it has entered a new Tracking Area.

**UMTS (Rel 11)**
* **SYSTEM_INFORMATION_BCH (RRC):** Legacy system information broadcasted over the Broadcast Channel.

### 4. Interpreting Timestamps
Please note that the timestamps provided in the summary tables below represent the total time elapsed for each Cause. This time window spans from the **first message** collected to the **last message** analyzed for that specific attack sequence.

---

## Summary of Results & Attack Vectors
Reviewers can use the tables below as an index to jump directly to specific timestamps within the `.txt` file to examine the corresponding RRC/NAS message sequences. The attacks are categorized by the injected NAS Reject Cause.

### 1. RAT Downgrade & Redirection
These events highlight the FBS successfully pushing the UE out of the secure 5G SA environment into legacy networks or degraded service states.

| Reject Cause | Transition Path | Timestamp Range | Attack Impact |
| :--- | :--- | :--- | :--- |
| **Cause 6** | 5G SA Release $\rightarrow$ UMTS (No Service) | `15:40:59.872` - `15:41:00.694` | Service Denial |
| **Cause 9** | 5G SA Release $\rightarrow$ LTE/5G NSA (Attach) | `15:45:49.605` - `15:45:50.040` | Forced 4G Downgrade |
| **Cause 10** | 5G SA Release $\rightarrow$ LTE/5G NSA (Attach) | `15:50:38.805` - `15:50:39.264` | Forced 4G Downgrade |
| **Cause 5** | 5G SA Release $\rightarrow$ LTE/5G NSA (TAU Request) | `15:54:50.242` - `15:54:50.509` | Forced 4G Downgrade |
| **Cause 7** | 5G SA Release $\rightarrow$ UMTS (No Service) | `15:57:10.171` - `15:57:10.879` | Service Denial |
| **Cause 13** | 5G SA Reg. Req. $\rightarrow$ UMTS SIB $\rightarrow$ LTE/5G NSA Attach | `16:13:12.021` - `16:13:13.188` | Forced 4G Downgrade |
| **Cause 15** | 5G SA Reg. Req. $\rightarrow$ 5G SA Registration Accept | `16:16:59.711` - `16:17:00.398` | Forced 5G SA New Cell with different Band |
| **Cause 27** | 5G SA Reg. Req. $\rightarrow$ LTE/5G NSA TAU Request | `16:22:38.495` - `16:22:39.030` | Forced 4G Downgrade |
| **Cause 72** | 5G SA Reg. Req. (x5) $\rightarrow$ LTE/5G NSA TAU Request | `16:28:37.348` - `16:29:18.338` | Forced 4G Downgrade |
| **Cause 20** | 5G SA Reg. Req. (x5) $\rightarrow$ LTE/5G NSA TAU Request | `16:33:15.389` - `16:33:56.425` | Forced 4G Downgrade |

### 2. State Disruption & DoS Loops
These events demonstrate the FBS locking the UE into persistent failure cycles.

| Reject Cause | Transition Path | Timestamp Range | Attack Impact |
| :--- | :--- | :--- | :--- |
| **Cause 11** | 5G SA Release $\rightarrow$ 5G SA Reject | `16:03:46.198` - `16:05:38.335` | **Loop** |
| **Cause 12** | 5G SA Reg. Request $\rightarrow$ 5G SA SIB1 | `16:06:59.663` - `16:10:17.153` | **Frozen** |
| **Cause 73** | 5G SA Reg. Req. $\rightarrow$ PDU Est. Req (x2) $\rightarrow$ FBS Cell Reselect | `17:10:53.038` - `17:13:56.630` | **Loop** |


> **IMSI Null Scheme Notice:** For Causes 12, 13, 15, 27, 72, 20, and 73, the Registration Procedure flow messages from the UE to the FBS have been provided. In all of the IDENTITY RESPONSE (NAS) messages, the UE sends its IMSI in cleartext. It is **important** to note that the SIM card used for this test is older (circa 2010) and may not have been provisioned with the cryptographic keys necessary to provide the SUCI in a concealed manner.

---

## Reviewer Guidelines
When analyzing `OP_A_Reject.txt`, reviewers should pay special attention to:
1.  **The Identity Response Context:** Search for timestamps from `16:06:59` onwards. Validate the message flow leading up to the `Identity Response` to observe how the UE bypasses SUCI configuration.
2.  **RRC Connection Handling:** Observe whether the FBS immediately releases the RRC connection after sending a NAS Reject, or if it holds the connection to manipulate the UE's cell reselection timers (particularly evident in the Cause 73 loop).