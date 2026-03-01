import React, { useState, useEffect } from "react";
import {
  Text,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
} from "react-native";
import * as MediaLibrary from "expo-media-library";
import { API_BASE, DEMO_USER_ID } from "@/constants/api";
import SearchBar from "@/components/ui/searchbar";
import PhotoGrid, { LocalPhoto } from "@/components/index/photogrid";
import PhotoModal from "@/components/index/photomodal";
import StatusBar from "@/components/index/statusbar";

const INDEX_LIMIT = 30; // index the N most recent photos on startup


export default function CameraRollScreen() {
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [indexDone, setIndexDone] = useState(0);
  const [indexTotal, setIndexTotal] = useState(0);
  const [selectedImage, setSelectedImage] = useState<LocalPhoto | null>(null);
  const [stage, setStage] = useState<"idle" | "clearing" | "uploading" | "processing" | "ready">("idle");
  const [searchResults, setSearchResults] = useState<LocalPhoto[] | null>(null);

  useEffect(() => {
    loadAndIndex();
  }, []);

  async function pollUntilReady(expected: number) {
    const maxWait = 120_000; // 2 minutes max
    const interval = 3_000;
    const deadline = Date.now() + maxWait;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, interval));
      try {
        const res = await fetch(`${API_BASE}/status/${DEMO_USER_ID}`);
        const { processed, total } = await res.json();
        console.log(`[status] ${processed}/${total} processed`);
        if (total > 0 && processed >= total) return;
      } catch (e) {
        console.warn("[status] poll failed:", e);
      }
    }
    console.warn("[status] timed out waiting for pipeline");
  }

  async function loadAndIndex() {
    const { status } = await MediaLibrary.requestPermissionsAsync();
    if (status !== "granted") {
      setPermissionDenied(true);
      setLoading(false);
      return;
    }

    const { assets } = await MediaLibrary.getAssetsAsync({
      mediaType: "photo",
      first: 100,
      sortBy: MediaLibrary.SortBy.creationTime,
    });

    setPhotos(assets.map((a) => ({ assetId: a.id, uri: a.uri })));
    setLoading(false);

    // 1. Clear old Snowflake data for this user before re-uploading
    setStage("clearing");
    try {
      await fetch(`${API_BASE}/clear/${DEMO_USER_ID}`, { method: "POST" });
    } catch { /* backend offline — continue anyway */ }

    // 2. Upload the most recent photos
    setStage("uploading");
    const toIndex = assets.slice(0, INDEX_LIMIT);
    setIndexTotal(toIndex.length);

    for (let i = 0; i < toIndex.length; i += 3) {
      const batch = toIndex.slice(i, i + 3);
      await Promise.all(batch.map(uploadAsset));
      setIndexDone((prev) => Math.min(prev + batch.length, toIndex.length));
    }

    // 3. Trigger AI pipeline on all uploaded photos
    setStage("processing");
    try {
      const res = await fetch(`${API_BASE}/reprocess/${DEMO_USER_ID}`, { method: "POST" });
      const data = await res.json();
      console.log("[reprocess] triggered:", data);
    } catch (e) {
      console.error("[reprocess] failed:", e);
    }

    // 4. Poll /status until all photos are processed
    await pollUntilReady(toIndex.length);
    setStage("ready");
  }

  async function triggerReprocess() {
    try {
      const res = await fetch(`${API_BASE}/reprocess/${DEMO_USER_ID}`, { method: "POST" });
      const data = await res.json();
      console.log("[reprocess]", data);
    } catch (e) {
      console.error("[reprocess] failed", e);
    }
  }

  async function loadMore() {
    const { assets } = await MediaLibrary.getAssetsAsync({
      mediaType: "photo",
      first: indexTotal + 100,
      sortBy: MediaLibrary.SortBy.creationTime,
    });

    setPhotos(assets.map((a) => ({ assetId: a.id, uri: a.uri })));

    // Auto-index the next batch of photos
    const toIndex = assets.slice(indexTotal, indexTotal + INDEX_LIMIT);
    const prev = indexTotal;
    setIndexTotal((prev) => prev + toIndex.length);

    for (let i = prev; i < prev + INDEX_LIMIT; i += 3) {
      const batch = toIndex.slice(i, i + 3);
      await Promise.all(batch.map(uploadAsset));
      setIndexDone((prev) => prev + batch.length);
    }
  }

  async function uploadAsset(asset: MediaLibrary.Asset) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      // getAssetInfoAsync resolves ph:// → file:// on iOS; fall back to asset.uri
      let uri = asset.uri;
      try {
        const info = await Promise.race([
          MediaLibrary.getAssetInfoAsync(asset),
          new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 3000)),
        ]);
        uri = info.localUri ?? asset.uri;
      } catch {
        // use asset.uri as-is
      }

      const formData = new FormData();
      formData.append("user_id", DEMO_USER_ID);
      formData.append("device_uri", asset.uri);  // on-device reference stored in Snowflake
      formData.append("file", { uri, name: asset.filename || "photo.jpg", type: "image/jpeg" } as any);

      const res = await fetch(`${API_BASE}/upload/`, { method: "POST", body: formData, signal: controller.signal });
      const data = await res.json();
      const photoId: string = data.photo_id;
      console.log('photo id is ', photoId);
      setPhotos((prevPhotos) =>
        prevPhotos.map((photo) =>
          photo.assetId === asset.id ? { ...photo, photoId } : photo
        )
      );
    } catch {
      // backend offline or timed out — progress still advances
    } finally {
      clearTimeout(timeout);
    }
  }

  async function handleSearch(text: string): Promise<void> {
    if (text.trim() === "") {
      setSearchResults(null);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/search/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, user_id: DEMO_USER_ID }),
      });

      const data = await response.json();
      const results: LocalPhoto[] = (data.photos ?? []).map((p: any) => ({
        assetId: p.id,
        photoId: p.id,
        uri: `${API_BASE}${p.storage_url}`,
      }));
      setSearchResults(results);
      console.log(`[search] "${text}" → ${results.length} results, labels:`, data.matched_labels);
    } catch (e) {
      console.error("[search] failed:", e);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1, backgroundColor: "#0a0a0a", paddingTop: 60, paddingHorizontal: 16 }}>
      <Text style={{ fontSize: 28, fontWeight: "700", color: "#fff", textAlign: "center", marginBottom: 8 }}>FotoFindr</Text>

      <StatusBar stage={stage} indexDone={indexDone} indexTotal={indexTotal} />

      {loading ? (
        <ActivityIndicator color="#6c63ff" style={{ marginTop: 40 }} />
      ) : permissionDenied ? (
        <Text style={{ color: "#aaa", textAlign: "center", marginTop: 60, fontSize: 15 }}>No photo access. Enable it in Settings → FotoFindr → Photos.</Text>
      ) : photos.length === 0 ? (
        <Text style={{ color: "#aaa", textAlign: "center", marginTop: 60, fontSize: 15 }}>No photos found on this device.</Text>
      ) : (
        <PhotoGrid
          photos={searchResults ?? photos}
          onPhotoPress={setSelectedImage}
          loadMore={searchResults ? () => {} : loadMore}
          filter={[]}
        />
      )}

      <PhotoModal
        visible={!!selectedImage}
        imageData={selectedImage!}
        labels={["Label 1", "Label 2", "Label 3"]}
        onClose={() => setSelectedImage(null)}
      />

      <SearchBar onSearch={handleSearch} />
    </KeyboardAvoidingView>
  );
}
