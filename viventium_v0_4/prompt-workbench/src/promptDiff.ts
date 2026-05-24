export function choosePromptDiffText({
  changed,
  currentPromptText,
  nextText,
  workingTreeChanged,
  workingTreeBaseText,
  selectedBaseText,
}: {
  changed: boolean;
  currentPromptText: string;
  nextText: string;
  workingTreeChanged: boolean;
  workingTreeBaseText?: string | null;
  selectedBaseText?: string | null;
}) {
  const hasSelectedBaseText = selectedBaseText !== undefined && selectedBaseText !== null;
  const hasWorkingTreeBaseText = workingTreeBaseText !== undefined && workingTreeBaseText !== null;
  return {
    original: hasSelectedBaseText
      ? selectedBaseText
      : changed
      ? currentPromptText
      : workingTreeChanged && hasWorkingTreeBaseText
        ? workingTreeBaseText
        : currentPromptText,
    modified: changed ? nextText : currentPromptText,
  };
}
