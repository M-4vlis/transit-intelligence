import type { PropsWithChildren } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, spacing } from '@/constants/theme';

interface ScreenProps extends PropsWithChildren {
  title: string;
  subtitle?: string;
  scroll?: boolean;
}

export function Screen({ title, subtitle, scroll = true, children }: ScreenProps) {
  const content = (
    <View style={styles.content}>
      <View style={styles.heading}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      {children}
    </View>
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
      {scroll ? <ScrollView contentContainerStyle={styles.scroll}>{content}</ScrollView> : content}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  scroll: { flexGrow: 1 },
  content: { flex: 1, padding: spacing.md, gap: spacing.md },
  heading: { gap: spacing.xs },
  title: { color: colors.text, fontSize: 28, lineHeight: 34, fontWeight: '800' },
  subtitle: { color: colors.muted, fontSize: 15, lineHeight: 21 },
});
