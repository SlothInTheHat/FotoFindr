import { Tabs } from "expo-router";
import React from "react";

import { HapticTab } from "@/components/haptic-tab";
import { IconSymbol } from "@/components/ui/icon-symbol";
import { Colors } from "@/constants/theme";
import { useColorScheme } from "@/hooks/use-color-scheme";

export default function TabLayout() {
  const colorScheme = useColorScheme();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors[colorScheme ?? "light"].tint,
        headerShown: false,
        tabBarButton: HapticTab,
        tabBarStyle: { backgroundColor: "#0a0a0a", borderTopColor: "#1a1a1a" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Camera Roll",
          tabBarIcon: ({ color }) => <IconSymbol size={24} name="photo.on.rectangle" color={color} />,
        }}
      />
      <Tabs.Screen
        name="cleanup"
        options={{
          title: "Cleanup",
          tabBarIcon: ({ color }) => <IconSymbol size={24} name="trash.fill" color={color} />,
        }}
      />
    </Tabs>
  );
}
