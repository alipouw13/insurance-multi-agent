# 04 - Register and Scan Microsoft Fabric Tenant

This document covers registering and scanning your Microsoft Fabric tenant in Microsoft Purview, based on the official Microsoft documentation.

> **Reference**: [Connect to your Microsoft Fabric tenant in the same tenant as Microsoft Purview](https://learn.microsoft.com/en-us/purview/register-scan-fabric-tenant)

---

## Overview

Scanning a Microsoft Fabric tenant brings in metadata and lineage from all Fabric items including Power BI. This provides unified governance across your entire Fabric environment.

## Prerequisites

- Please note, Sthat for all Fabric items besides Power BI, only item level metadata and lineage can be scanned.
- For Lakehouse tables and files, sub-item level metadata scanning is available in preview but sub-item level lineage is still not supported.
- Add the Purview Managed Identity to a security group
- In the Fabric admin protal > Tenant settings > Admin APIs > enable _Service Principals can access read-only admin APIs_ and add the security group you just created
- Also ensure _Enhance admin APIs responses with detailed metadata_ and _Enhance admin API responses with DAX mashup expressions_ are enabled

## Steps

Review [these steps](https://learn.microsoft.com/en-us/purview/register-scan-fabric-tenant?tabs=Scenario1) to scan storage accountsyour Fabric tenant. Ensure you review additional [pre-requisites](https://learn.microsoft.com/en-us/purview/register-scan-fabric-tenant?tabs=Scenario1#prerequisites) and understand the [limitations](https://learn.microsoft.com/en-us/purview/register-scan-fabric-tenant?tabs=Scenario1#known-limitations) before executing the scan.