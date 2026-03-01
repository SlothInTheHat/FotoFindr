import { View, TextInput, Pressable, StyleSheet } from "react-native";
import { IconSymbol } from "./icon-symbol";
import { useState } from "react";

export default function SearchBar({ onSearch }: { onSearch: (text: string) => void }) {
    const [textValue, setTextValue] = useState("");

    return (
        <View style={styles.searchBox}>
            <TextInput
                placeholder="Search photos..."
                placeholderTextColor="#666"
                style={styles.input}
                value={textValue}
                onChangeText={setTextValue}
                onSubmitEditing={(e) => onSearch(e.nativeEvent.text)}
            />
            <Pressable
                onPress={() => onSearch(textValue)}
                style={({ pressed }) => [
                    styles.searchButton,
                    { opacity: pressed ? 0.6 : 1 }
                ]}
            >
                <IconSymbol size={14} name="magnifyingglass" color={"#666"} />
            </Pressable>
        </View>
    );
}

const styles = StyleSheet.create({
    searchBox: { flexDirection: "row", alignItems: "center", marginVertical: 16, gap: 8 },
    input: { flex: 1, backgroundColor: "#1a1a1a", color: "#fff", paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, fontSize: 14 },
    searchButton: { backgroundColor: "#222", paddingHorizontal: 12, paddingVertical: 12, borderRadius: 8, justifyContent: "center", alignItems: "center" },
    searchButtonText: { fontSize: 18 },
});