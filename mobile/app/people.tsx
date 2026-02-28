/**
 * People Tab — view face clusters and assign names.
 */

import { useState, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  TextInput,
  Modal,
  Image,
  ActivityIndicator,
} from "react-native";
import { API_BASE, DEMO_USER_ID } from "../constants/api";

interface Person {
  id: string;
  name: string | null;
  photo_count: number;
  cover_photo_url: string | null;
}

export default function PeopleScreen() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [nameInput, setNameInput] = useState("");

  const fetchPeople = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/profiles/${DEMO_USER_ID}`);
      const data = await resp.json();
      setPeople(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPeople(); }, []);

  const assignName = async () => {
    if (!selectedPerson || !nameInput.trim()) return;
    await fetch(`${API_BASE}/profiles/${selectedPerson.id}/name`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: nameInput.trim() }),
    });
    setPeople((prev) =>
      prev.map((p) => (p.id === selectedPerson.id ? { ...p, name: nameInput.trim() } : p))
    );
    setSelectedPerson(null);
    setNameInput("");
  };

  if (loading) return <ActivityIndicator color="#6C63FF" style={{ flex: 1 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>{people.length} people detected</Text>

      <FlatList
        data={people}
        keyExtractor={(item) => item.id}
        numColumns={2}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card} onPress={() => { setSelectedPerson(item); setNameInput(item.name ?? ""); }}>
            <View style={styles.avatar}>
              {item.cover_photo_url ? (
                <Image source={{ uri: item.cover_photo_url }} style={styles.avatarImg} />
              ) : (
                <Text style={styles.avatarPlaceholder}>?</Text>
              )}
            </View>
            <Text style={styles.name}>{item.name ?? "Unnamed"}</Text>
            <Text style={styles.count}>{item.photo_count} photos</Text>
          </TouchableOpacity>
        )}
      />

      {/* Name assignment modal */}
      <Modal visible={!!selectedPerson} transparent animationType="fade">
        <View style={styles.overlay}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Who is this?</Text>
            <TextInput
              style={styles.nameInput}
              value={nameInput}
              onChangeText={setNameInput}
              placeholder="Enter name..."
              placeholderTextColor="#555"
              autoFocus
            />
            <TouchableOpacity style={styles.saveBtn} onPress={assignName}>
              <Text style={styles.saveBtnText}>Save</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setSelectedPerson(null)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f0f0f", padding: 12 },
  heading: { color: "#aaa", fontSize: 13, marginBottom: 12 },
  card: { flex: 1 / 2, margin: 4, backgroundColor: "#1a1a1a", borderRadius: 12, padding: 12, alignItems: "center" },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: "#2a2a2a", justifyContent: "center", alignItems: "center", marginBottom: 8, overflow: "hidden" },
  avatarImg: { width: "100%", height: "100%" },
  avatarPlaceholder: { color: "#555", fontSize: 28 },
  name: { color: "#fff", fontWeight: "700", fontSize: 14 },
  count: { color: "#666", fontSize: 12 },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", justifyContent: "center", alignItems: "center" },
  modal: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 24, width: "80%" },
  modalTitle: { color: "#fff", fontSize: 18, fontWeight: "700", marginBottom: 16 },
  nameInput: { backgroundColor: "#0f0f0f", color: "#fff", borderRadius: 10, padding: 12, fontSize: 16, marginBottom: 16 },
  saveBtn: { backgroundColor: "#6C63FF", borderRadius: 10, padding: 14, alignItems: "center", marginBottom: 8 },
  saveBtnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  cancelText: { color: "#666", textAlign: "center", padding: 8 },
});
