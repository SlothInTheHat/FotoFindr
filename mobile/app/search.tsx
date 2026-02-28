/**
 * Search Tab — natural language photo search with ElevenLabs narration.
 */

import { useState, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  Image,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { Audio } from "expo-av";
import { API_BASE, DEMO_USER_ID } from "../constants/api";

interface PhotoResult {
  id: string;
  storage_url: string;
  caption: string;
  tags: string[];
  emotions: { dominant: string }[];
  importance_score: number;
}

const SUGGESTED_QUERIES = [
  "Photos where I look happy",
  "Pictures with my dog",
  "Unimportant screenshots",
  "Photos at the beach",
];

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PhotoResult[]>([]);
  const [narrationText, setNarrationText] = useState("");
  const [loading, setLoading] = useState(false);
  const soundRef = useRef<Audio.Sound | null>(null);

  const search = async (q: string = query) => {
    if (!q.trim()) return;
    setLoading(true);
    setResults([]);
    setNarrationText("");

    try {
      const resp = await fetch(`${API_BASE}/search/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, user_id: DEMO_USER_ID, limit: 20 }),
      });
      const data = await resp.json();
      setResults(data.photos ?? []);
      setNarrationText(data.narration_text ?? "");

      if (data.narration) {
        await playNarration(data.narration);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const playNarration = async (url: string) => {
    if (soundRef.current) {
      await soundRef.current.unloadAsync();
    }
    const { sound } = await Audio.Sound.createAsync({ uri: url }, { shouldPlay: true });
    soundRef.current = sound;
  };

  return (
    <View style={styles.container}>
      {/* Search bar */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          placeholder="Find photos of Jake at the beach..."
          placeholderTextColor="#555"
          returnKeyType="search"
          onSubmitEditing={() => search()}
        />
        <TouchableOpacity style={styles.searchBtn} onPress={() => search()}>
          <Text style={styles.searchBtnText}>Go</Text>
        </TouchableOpacity>
      </View>

      {/* Suggestions */}
      {results.length === 0 && !loading && (
        <View style={styles.suggestions}>
          {SUGGESTED_QUERIES.map((q) => (
            <TouchableOpacity key={q} style={styles.chip} onPress={() => { setQuery(q); search(q); }}>
              <Text style={styles.chipText}>{q}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Narration banner */}
      {narrationText ? (
        <View style={styles.narrationBanner}>
          <Text style={styles.narrationText}>🔊 {narrationText}</Text>
        </View>
      ) : null}

      {loading && <ActivityIndicator color="#6C63FF" style={{ marginTop: 32 }} />}

      {/* Results grid */}
      <FlatList
        data={results}
        keyExtractor={(item) => item.id}
        numColumns={2}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Image source={{ uri: item.storage_url }} style={styles.cardImg} />
            {item.emotions?.[0]?.dominant && (
              <View style={styles.emotionBadge}>
                <Text style={styles.emotionText}>{item.emotions[0].dominant}</Text>
              </View>
            )}
            <Text style={styles.caption} numberOfLines={2}>{item.caption}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f0f0f", padding: 12 },
  searchRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  input: {
    flex: 1,
    backgroundColor: "#1a1a1a",
    color: "#fff",
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
  },
  searchBtn: {
    backgroundColor: "#6C63FF",
    borderRadius: 10,
    paddingHorizontal: 16,
    justifyContent: "center",
  },
  searchBtnText: { color: "#fff", fontWeight: "700" },
  suggestions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  chip: { backgroundColor: "#1a1a1a", borderRadius: 20, paddingVertical: 6, paddingHorizontal: 12 },
  chipText: { color: "#aaa", fontSize: 12 },
  narrationBanner: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: "#6C63FF",
  },
  narrationText: { color: "#ccc", fontSize: 13 },
  card: { flex: 1 / 2, margin: 4, backgroundColor: "#1a1a1a", borderRadius: 10, overflow: "hidden" },
  cardImg: { width: "100%", aspectRatio: 1 },
  emotionBadge: {
    position: "absolute",
    top: 6,
    right: 6,
    backgroundColor: "rgba(108,99,255,0.85)",
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  emotionText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  caption: { color: "#aaa", fontSize: 11, padding: 6 },
});
