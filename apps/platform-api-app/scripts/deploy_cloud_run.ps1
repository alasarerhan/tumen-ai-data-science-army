$ErrorActionPreference = 'Stop'

param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [Parameter(Mandatory = $true)][string]$Region,
  [Parameter(Mandatory = $false)][string]$ServiceName = "platform-api",
  [Parameter(Mandatory = $false)][string]$Repository = "platform-api",
  [Parameter(Mandatory = $false)][string]$ImageTag = "latest"
)

$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/$ServiceName`:$ImageTag"

Write-Host "[deploy] Build image: $Image"
gcloud builds submit --project $ProjectId --tag $Image .

Write-Host "[deploy] Deploy Cloud Run service: $ServiceName"
gcloud run deploy $ServiceName `
  --project $ProjectId `
  --region $Region `
  --image $Image `
  --platform managed `
  --allow-unauthenticated=false

Write-Host "[deploy] Done. Configure secrets/env vars after deploy as per checklist."
