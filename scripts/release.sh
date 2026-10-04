#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# SafeEyes for macOS — Release Packaging Script
# Archive -> Developer ID Sign -> Notarize -> Staple -> DMG
# ==============================================================================

SCHEME="SafeEyes"
BUNDLE_ID="com.safeeyes.app"
APP_NAME="SafeEyes"
BUILD_DIR="$(pwd)/build/release"
ARCHIVE_PATH="${BUILD_DIR}/${APP_NAME}.xcarchive"
EXPORT_PATH="${BUILD_DIR}/export"
APP_PATH="${EXPORT_PATH}/${APP_NAME}.app"
DMG_PATH="${BUILD_DIR}/${APP_NAME}.dmg"

DEVELOPER_ID_APPLICATION="${DEVELOPER_ID_APPLICATION:-}"
NOTARY_KEYCHAIN_PROFILE="${NOTARY_KEYCHAIN_PROFILE:-}"
NOTARY_APPLE_ID="${NOTARY_APPLE_ID:-}"
NOTARY_PASSWORD="${NOTARY_PASSWORD:-}"
NOTARY_TEAM_ID="${NOTARY_TEAM_ID:-}"

echo "==> 1. Regenerating Xcode project with XcodeGen..."
xcodegen generate

echo "==> 2. Cleaning and creating build directories..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${EXPORT_PATH}"

echo "==> 3. Archiving ${SCHEME}..."
xcodebuild archive \
    -project "${APP_NAME}.xcodeproj" \
    -scheme "${SCHEME}" \
    -configuration Release \
    -archivePath "${ARCHIVE_PATH}" \
    SKIP_INSTALL=NO \
    BUILD_LIBRARY_FOR_DISTRIBUTION=YES

echo "==> 4. Extracting app bundle from archive..."
cp -R "${ARCHIVE_PATH}/Products/Applications/${APP_NAME}.app" "${EXPORT_PATH}/"

if [ -n "${DEVELOPER_ID_APPLICATION}" ]; then
    echo "==> 5. Signing application bundle with Developer ID: ${DEVELOPER_ID_APPLICATION}..."
    codesign --force --deep --options runtime \
        --entitlements "SafeEyes/Support/SafeEyes.entitlements" \
        --sign "${DEVELOPER_ID_APPLICATION}" \
        "${APP_PATH}"

    echo "==> Verifying signature..."
    codesign --verify --verbose=4 "${APP_PATH}"
    spctl --assess --type execute --verbose=4 "${APP_PATH}"

    # Zip for notarization
    ZIP_PATH="${BUILD_DIR}/${APP_NAME}.zip"
    ditto -c -k --keepParent "${APP_PATH}" "${ZIP_PATH}"

    echo "==> 6. Submitting for notarization via notarytool..."
    if [ -n "${NOTARY_KEYCHAIN_PROFILE}" ]; then
        xcrun notarytool submit "${ZIP_PATH}" --keychain-profile "${NOTARY_KEYCHAIN_PROFILE}" --wait
    elif [ -n "${NOTARY_APPLE_ID}" ] && [ -n "${NOTARY_PASSWORD}" ] && [ -n "${NOTARY_TEAM_ID}" ]; then
        xcrun notarytool submit "${ZIP_PATH}" \
            --apple-id "${NOTARY_APPLE_ID}" \
            --password "${NOTARY_PASSWORD}" \
            --team-id "${NOTARY_TEAM_ID}" \
            --wait
    else
        echo "WARNING: Notary credentials not set. Skipping notarization."
    fi

    echo "==> 7. Stapling notarization ticket to app bundle..."
    xcrun stapler staple "${APP_PATH}"
else
    echo "NOTICE: DEVELOPER_ID_APPLICATION not provided. Skipping codesigning and notarization."
fi

echo "==> 8. Building DMG..."
hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${APP_PATH}" \
    -ov -format UDZO \
    "${DMG_PATH}"

if [ -n "${DEVELOPER_ID_APPLICATION}" ]; then
    echo "==> 9. Signing and stapling DMG..."
    codesign --force --sign "${DEVELOPER_ID_APPLICATION}" "${DMG_PATH}"
    xcrun stapler staple "${DMG_PATH}" || true
fi

echo "==> Release artifact created successfully at: ${DMG_PATH}"
