Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Read-Json($relativePath) {
    $path = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing expected asset: $relativePath"
    }
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
}

function Assert-Equal($actual, $expected, $message) {
    if ($actual -ne $expected) {
        throw "$message Expected '$expected', got '$actual'."
    }
}

function Test-Property($object, $name) {
    return $null -ne $object -and $null -ne ($object.PSObject.Properties[$name])
}

function Assert-ContainsRoleIds($config, $expectedRoleIds, $message) {
    $roleIds = @($config.RoleIds)
    foreach ($expectedRoleId in $expectedRoleIds) {
        if ($roleIds -notcontains $expectedRoleId) {
            throw "$message Missing '$expectedRoleId'."
        }
    }
}

$wildRoles = @{
    "Server/NPC/Roles/AlecsCats/Mobs/Cat.json" = "Cat_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Longhair.json" = "Cat_Longhair_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Shorthair.json" = "Cat_Shorthair_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Bobtail.json" = "Cat_Bobtail_Pet"
}

foreach ($entry in $wildRoles.GetEnumerator()) {
    $role = Read-Json $entry.Key
    Assert-Equal $role.Parameters.TamedRoleId.Value $entry.Value "$($entry.Key) has an incorrect tame target."
}

$tempInteraction = Read-Json "Server/Tamework/Interactions/ACIntCatTemp.json"
Assert-ContainsRoleIds $tempInteraction @("Cat", "Cat_Longhair", "Cat_Shorthair", "Cat_Bobtail") "ACIntCatTemp.json should apply to every wild cat body role."

$tameInteraction = $tempInteraction.Interactions | Where-Object { $_.Type -eq "Tame" } | Select-Object -First 1
if ($null -eq $tameInteraction) {
    throw "ACIntCatTemp.json is missing its Tame interaction."
}
Assert-Equal $tameInteraction.Role "Cat_Pet" "ACIntCatTemp.json should keep Cat_Pet as its literal fallback."
Assert-Equal $tameInteraction.RoleParam "TamedRoleId" "ACIntCatTemp tame interaction must resolve the per-role tame target."

$setRoleEffects = @()
foreach ($interaction in $tempInteraction.Interactions) {
    if ((Test-Property $interaction "Effects") -and (Test-Property $interaction.Effects "SetRole")) {
        $setRoleEffects += $interaction.Effects.SetRole
    }
}
if ($setRoleEffects.Count -lt 2) {
    throw "ACIntCatTemp.json should keep feed and mode-cycle SetRole repair effects."
}
foreach ($effect in $setRoleEffects) {
    Assert-Equal $effect.Role "Cat_Pet" "ACIntCatTemp SetRole effects should keep Cat_Pet as their literal fallback."
    Assert-Equal $effect.RoleParam "TamedRoleId" "ACIntCatTemp SetRole effects must resolve the per-role tame target."
}

Write-Host "Cat tame role wiring validated."
