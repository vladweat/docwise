export function scrollToLatestToastStack(
  element: Pick<HTMLElement, "scrollHeight" | "scrollTop"> | null,
) {
  if (element) element.scrollTop = element.scrollHeight;
}
