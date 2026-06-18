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

function Assert-DoesNotHaveProperty($object, $name, $message) {
    if (Test-Property $object $name) {
        throw $message
    }
}

function Assert-SingleRoleId($config, $expectedRoleId, $message) {
    $roleIds = @($config.RoleIds)
    if ($roleIds.Count -ne 1 -or $roleIds[0] -ne $expectedRoleId) {
        throw "$message Expected only '$expectedRoleId', got '$($roleIds -join "', '")'."
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
Assert-SingleRoleId $tempInteraction "Cat" "ACIntCatTemp.json should only apply to the base wild cat role."

$tameInteraction = $tempInteraction.Interactions | Where-Object { $_.Type -eq "Tame" } | Select-Object -First 1
if ($null -eq $tameInteraction) {
    throw "ACIntCatTemp.json is missing its Tame interaction."
}
Assert-Equal $tameInteraction.Role "Cat_Pet" "ACIntCatTemp.json must fall back to the base pet role."

$variantConfigs = @(
    @{
        Path = "Server/Tamework/Interactions/ACIntCatLonghairTemp.json"
        WildRole = "Cat_Longhair"
        PetRole = "Cat_Longhair_Pet"
    },
    @{
        Path = "Server/Tamework/Interactions/ACIntCatShorthairTemp.json"
        WildRole = "Cat_Shorthair"
        PetRole = "Cat_Shorthair_Pet"
    },
    @{
        Path = "Server/Tamework/Interactions/ACIntCatBobtailTemp.json"
        WildRole = "Cat_Bobtail"
        PetRole = "Cat_Bobtail_Pet"
    }
)

foreach ($variant in $variantConfigs) {
    $config = Read-Json $variant.Path
    Assert-SingleRoleId $config $variant.WildRole "$($variant.Path) should only apply to its matching wild role."
    Assert-Equal $config.Priority 10 "$($variant.Path) should outrank the shared base temp config."

    $variantTameInteraction = $config.Interactions | Where-Object { $_.Type -eq "Tame" } | Select-Object -First 1
    if ($null -eq $variantTameInteraction) {
        throw "$($variant.Path) is missing its Tame interaction."
    }
    Assert-Equal $variantTameInteraction.Role $variant.PetRole "$($variant.Path) must tame into the matching pet role."
    Assert-DoesNotHaveProperty $variantTameInteraction "RoleParam" "$($variant.Path) tame interaction must use an explicit role instead of RoleParam."

    $setRoleEffects = @()
    foreach ($interaction in $config.Interactions) {
        if ((Test-Property $interaction "Effects") -and (Test-Property $interaction.Effects "SetRole")) {
            $setRoleEffects += $interaction.Effects.SetRole
        }
    }
    if ($setRoleEffects.Count -lt 2) {
        throw "$($variant.Path) should keep feed and mode-cycle SetRole repair effects."
    }
    foreach ($effect in $setRoleEffects) {
        Assert-Equal $effect.Role $variant.PetRole "$($variant.Path) SetRole effects must repair into the matching pet role."
        Assert-DoesNotHaveProperty $effect "RoleParam" "$($variant.Path) SetRole effects must use explicit roles instead of RoleParam."
    }
}

Write-Host "Cat tame role wiring validated."
