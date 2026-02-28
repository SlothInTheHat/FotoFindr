import { View, TextInput, Pressable, StyleSheet } from "react-native";
import { IconSymbol } from "./icon-symbol";

export default function SearchBar() {
    return (
        <View style={styles.searchBox}>
            <TextInput
                placeholder="Search photos..."
                placeholderTextColor="#666"
                style={styles.input}
            />
            <Pressable onPress={() => { }} style={styles.searchButton}>
                <IconSymbol size={14} name="magnifyingglass" color={"#666"} />
            </Pressable>
        </View>
    );
}

const styles = StyleSheet.create({
    searchBox: { flexDirection: "row", alignItems: "center", marginBottom: 16, gap: 8 },
    input: { flex: 1, backgroundColor: "#1a1a1a", color: "#fff", paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, fontSize: 14 },
    searchButton: { backgroundColor: "#222", paddingHorizontal: 12, paddingVertical: 12, borderRadius: 8, justifyContent: "center", alignItems: "center" },
    searchButtonText: { fontSize: 18 },
});